# GPU Cleaner Controller for Kubernetes 🚀

## Overview
GPU Resource Manager is a Kubernetes controller written in Python designed to optimize the utilization of GPU resources within a Kubernetes cluster. 
It automatically identifies and deletes deployments, jobs, or pods that are blocking GPU resources but are idle. 
This helps in maximizing the availability of GPU resources for active workloads and improves the overall efficiency of the cluster. 🎯

* 📊 Monitors deployments, jobs, and pods for GPU usage.
* 🗑️ Automatically deletes idle workloads that are consuming GPU resources.
* ⏱️ Configurable idle timeout duration.
* 🛡️ Excludes specified important workloads from deletion.
* 📝 Logs actions and resource status for audit and debugging purposes.

## Installation

### Build Dockerimage from source
``` 
git clone https://github.com/paul-grundmann/k8s-gpu-cleaner-controller.git .
cd k8s-gpu-cleaner-controller/
docker buildx build --push --platform linux/amd64 -t  registry.datexis.com/pgrundmann/gpu-cleaner-controller:0.1 .
kubectl create -f deployment/rbac.yaml deployment/controller.yaml
```

## Configuration

The GPU Resource Manager can be configured using environment variables:

    GPU_UTIL_INTERVAL: The interval used to decide whether to delete workloads if idle (default is 1h).
    IMPORTANT_WORKLOADS: Comma-separated list of workload names that should not be deleted.
    FORBID_DELETE_LABEL: The label used to mark workloads that should not be deleted automatically.

### Example:
```
GPU_UTIL_INTERVAL="1h"
export IMPORTANT_WORKLOADS="important-deployment-1,important-deployment-2"
export FORBID_DELETE_LABEL="do-not-delete"
```

Contributing

Contributions are welcome! Please open an issue or submit a pull request for any bug fixes, improvements, or new features. 🚀

1. Fork the repository 
2. Create your feature branch (git checkout -b feature/your-feature)
3. Commit your changes (git commit -am 'Add some feature')
4. Push to the branch (git push origin feature/your-feature)
5. Open a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

Thank you for using GPU Resource Manager! If you have any questions or feedback, please feel free to open an issue. Happy optimizing!
