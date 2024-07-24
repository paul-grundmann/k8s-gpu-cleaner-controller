import os
import time
from datetime import datetime
from kubernetes import client, config
from kubernetes.client import AppsV1Api
from prometheus_api_client import PrometheusConnect
import logging
from pytimeparse.timeparse import timeparse

logger = logging.getLogger(__name__)

def main():
    # the interval used to decide whether to delete workloads if idle
    gpu_utilization_average_interval = os.getenv("GPU_UTIL_INTERVAL", "1h")

    # List of workload names that shall not be deleted
    important_deployments_not_to_delete = os.getenv("IMPORTANT_WORKLOADS", "")

    # set the respective environment variable as a label for workloads that shall not be deleted automatically
    FORBID_DELETE_LABEL = os.getenv("FORBID_DELETE_LABEL", "")
    config.load_kube_config()

    core_v1 = client.CoreV1Api()
    apps_v1 = AppsV1Api()

    prom = PrometheusConnect(url="https://prometheus.datexis.com", disable_ssl=False)

    while True:
        gpu_util_over_interval = prom.custom_query(
            query=f"avg by (pod, namespace) (avg_over_time(dcgm_gpu_utilization[{gpu_utilization_average_interval}]))")

        # remove empty metrics
        gpu_util_over_interval = list(filter(lambda x: len(x["metric"]) > 0, gpu_util_over_interval))

        # get deployments or jobs for the pods if they exist
        # kubectl describe pod "podname"
        for metric in gpu_util_over_interval:
            pod_name = metric["metric"]["pod"]
            namespace = metric["metric"]["namespace"]
            value = float(metric["value"][1])
            pod = core_v1.read_namespaced_pod(pod_name, namespace)
            owner_references = pod.metadata.owner_references

            if FORBID_DELETE_LABEL in pod.metadata.labels:
                logger.info(f"Dont delete: {pod_name} because it has the {FORBID_DELETE_LABEL} label")
                continue

            if value > 0.01:
                logger.info(f"Dont delete: {pod_name} because it uses the GPU")
                continue
            try:
                started_at_timestamp = pod.status.container_statuses[0].state.running.started_at
                started_at_timestamp = started_at_timestamp.replace(tzinfo=None)
                current_time = datetime.now()
                running_time = current_time - started_at_timestamp
                if running_time.seconds < timeparse(gpu_utilization_average_interval):
                    # ignore pod until the container runs for at least
                    logger.info(f"Dont delete: {pod_name} because it runs shorter than {gpu_utilization_average_interval}")
                    continue
            except:
                logger.error(f"Could not get started-timestamp of pod: {pod_name}")

            if owner_references is not None:
                # get replicaset, deployment or job
                if owner_references[0].kind == "ReplicaSet":
                    replicaset = apps_v1.read_namespaced_replica_set(owner_references[0].name, namespace)
                    deployment_name = replicaset.metadata.owner_references[0].name
                    logger.info(f"Shall delete Deployment: {deployment_name}")

                elif owner_references[0].kind == "Job":
                    # delete job object
                    job_name = owner_references[0].name
                    logger.info(f"Shall delete Job: {job_name}")
            else:
                # delete pod directly
                logger.info(f"Shall delete pod: {pod_name}")
        time.sleep(10)

if __name__ == "__main__":
    main()
