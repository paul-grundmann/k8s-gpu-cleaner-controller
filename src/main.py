import os
import time
from datetime import datetime
from kubernetes import client, config
from kubernetes.client import AppsV1Api, BatchV1Api, V1Pod
from prometheus_api_client import PrometheusConnect
import logging
import sys
from pytimeparse.timeparse import timeparse
import uuid
from datetime import datetime
import pytz

logging.basicConfig(
    level=os.environ.get('LOGLEVEL', 'INFO').upper(),
    datefmt='%Y-%m-%d %H:%M:%S',
    format='%(asctime)s %(levelname)-8s %(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler('/tmp/gpu-cleaner.log')]
)
logger = logging.getLogger(__name__)


def main():
    # the interval used to decide whether to delete workloads if idle
    gpu_utilization_average_interval = os.getenv("GPU_UTIL_INTERVAL", "1h")

    # List of workload names that shall not be deleted
    important_deployments_not_to_delete = os.getenv("IMPORTANT_WORKLOADS", "")

    # set the respective environment variable as a label for workloads that shall not be deleted automatically
    FORBID_DELETE_LABEL = os.getenv("FORBID_DELETE_LABEL", "gpu-cleaner:allow-gpu-idle")
    FORBID_DELETE_LABEL_KEY, FORBID_DELETE_LABEL_VALUE = FORBID_DELETE_LABEL.split(":")

    IGNORED_GPU_TYPES = [x.strip() for x in os.getenv("IGNORED_GPU_TYPES", "K80,P100,L40").split(",")]

    if os.getenv("LOCAL_DEV", None) is not None:
        config.load_kube_config()
    else:
        config.load_incluster_config()

    core_v1 = client.CoreV1Api()
    apps_v1 = AppsV1Api()
    batch_v1 = BatchV1Api()

    prom = PrometheusConnect(url="https://prometheus.datexis.com", disable_ssl=False)

    while True:
        gpu_util_over_interval = prom.custom_query(
            query=f"avg by (pod, namespace, gpu) (avg_over_time(DCGM_FI_DEV_GPU_UTIL[{gpu_utilization_average_interval}]))")

        # remove empty metrics
        gpu_util_over_interval = list(filter(lambda x: "pod" in x["metric"], gpu_util_over_interval))

        # get deployments or jobs for the pods if they exist
        # kubectl describe pod "podname"
        for metric in gpu_util_over_interval:
            pod_name = metric["metric"]["pod"]
            namespace = metric["metric"]["namespace"]
            value = float(metric["value"][1])
            try:
                pod: V1Pod = core_v1.read_namespaced_pod(pod_name, namespace)
            except Exception as e:
                logger.error(f"Exception while trying to get pod resource of pod {pod_name}. Exception: {e}")
                continue
            owner_references = pod.metadata.owner_references

            if pod.metadata.labels is not None:
                if FORBID_DELETE_LABEL_KEY in pod.metadata.labels:
                    if FORBID_DELETE_LABEL_VALUE == pod.metadata.labels[FORBID_DELETE_LABEL_KEY]:
                        logger.info(f"Do not delete: {pod_name} because it has the {FORBID_DELETE_LABEL} label")
                        continue

            if value > 0.01:
                logger.info(f"Do not delete: {pod_name} because it uses the GPU")
                continue

            if hasattr(pod.spec, 'node_selector'):
                if pod.spec.node_selector is not None:
                    if "gpu" in pod.spec.node_selector:
                        if any([pod.spec.node_selector["gpu"].lower() == gpu_type.lower() for gpu_type in IGNORED_GPU_TYPES]):
                            logger.info(f"Do not delete: {pod_name} because it operates on ignored GPU types")
                            continue


            if pod.status.container_statuses[0].state.running is not None:
                try:
                    started_at_timestamp = pod.status.container_statuses[0].state.running.started_at
                    started_at_timestamp = started_at_timestamp.replace(tzinfo=None)
                    current_time = datetime.now()
                    running_time = current_time - started_at_timestamp
                    if running_time.total_seconds() < timeparse(gpu_utilization_average_interval):
                        logger.info(
                            f"Do not delete: {pod_name} because it runs only for {running_time.total_seconds()} seconds, shorter than {timeparse(gpu_utilization_average_interval)}")
                        continue
                except Exception as e:
                    logger.error(f"Could not get started-timestamp of pod: {pod_name}, exception: {e}")
                    continue
            else:
                # pod not running yet
                continue
            if owner_references is not None:
                # get replicaset, deployment or job
                if owner_references[0].kind == "ReplicaSet":
                    try:
                        replicaset = apps_v1.read_namespaced_replica_set(owner_references[0].name, namespace)
                        deployment_name = replicaset.metadata.owner_references[0].name
                        apps_v1.patch_namespaced_deployment_scale(deployment_name, namespace,{'spec': {'replicas': 0}})
                        logger.info(f"Scaled down deployment: {deployment_name}")
                        event_metadata = client.V1ObjectMeta(
                            name=f"{deployment_name}.{str(uuid.uuid4())}",
                            namespace=namespace
                        )

                        # Reference the Deployment in involvedObject
                        involved_object = client.V1ObjectReference(
                            api_version="apps/v1",
                            kind="Deployment",
                            name=deployment_name,
                            namespace=namespace,
                            uid=deployment.metadata.uid
                        )

                        # Create the Event
                        event = client.CoreV1Event(
                            metadata=event_metadata,
                            involved_object=involved_object,
                            first_timestamp=datetime.now(pytz.utc),
                            reason="IdleGPUScaledownEvent",
                            message=f"The deployment was scaled down to 0 replicas after detecting over {gpu_utilization_average_interval} of GPU inactivity.",
                            type="Warning"
                        )
                        core_v1.create_namespaced_event(namespace=namespace, body=event)
                        logger.info(f"Created event with scaledown notification for deployment: {deployment_name}")
                    except Exception as e:
                        logger.error(f"Exception while trying to delete deployment: {e}")
                        continue
                elif owner_references[0].kind == "Job":
                    # delete job object
                    try:
                        job_name = owner_references[0].name
                        batch_v1.delete_namespaced_job(job_name, namespace)
                        logger.info(f"Deleted job: {job_name}")
                    except Exception as e:
                        logger.error(f"Exception while trying to delete job: {e}")
                        continue
            else:
                # delete pod directly
                try:
                    core_v1.delete_namespaced_pod(pod_name, namespace)
                    logger.info(f"Deleted: {pod_name}")
                except Exception as e:
                    logger.error(f"Exception: {e} Could not delete pod: {pod_name}")
                    continue
        time.sleep(10)


if __name__ == "__main__":
    main()
