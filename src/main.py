import os
import time

from kubernetes import client, config
from kubernetes.client import AppsV1Api
from prometheus_api_client import PrometheusConnect
import logging

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
            if value > 0.01:
                continue

            test = core_v1.read_namespaced_pod(pod_name, namespace)
            owner_references = test.metadata.owner_references

            if owner_references is not None:
                # get replicaset, deployment or job
                if owner_references[0].kind == "ReplicaSet":
                    replicaset = apps_v1.read_namespaced_replica_set(owner_references[0].name, namespace)
                    deployment_name = replicaset.metadata.owner_references[0].name
                    logger.info(f"Shall delete Deployment: {deployment_name}")
                    # delete deployment object

                    pass
                    # get replicaset owner_references
                elif owner_references[0].kind == "Job":
                    # delete job object
                    job_name = owner_references[0].name
                    logger.info(f"Shall delete Job: {job_name}")
                    a = 0
            else:
                # delete pod directly
                logger.info(f"Shall delete pod: {pod_name}")
                pass
        time.sleep(10)


# Program Loop:
# 1. Query all pods consuming a GPU, exported via dcgm_exporter
# 2. Exclude all pods from a configmap / with an annotation from further processing
# 3. Get average GPU utilization over 1h
# 3a) if avg by (pod) (avg_over_time(dcgm_gpu_utilization[10m])) if pod is 0 -> Check:
# 4) Get the deployment / job of the pod if it is not a single pod
# 5) Delete the respective resource (Deployment, Job or Pod)


if __name__ == "__main__":
    main()
