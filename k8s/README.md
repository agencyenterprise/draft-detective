# AI Reviewer - Kubernetes Deployment

Simple, plug-and-play Kubernetes deployment for AI Reviewer.  
**Optimized for OpenShift** with support for vanilla Kubernetes.

## Prerequisites

- Kubernetes cluster (1.24+) or OpenShift (4.10+)
- `kubectl` or `oc` CLI
- Container registry access (Quay.io, Docker Hub, GitHub Container Registry, etc.)
- Your API keys (OpenAI, Langfuse, etc.)

## Quick Start

### 1. Build and Push Container Images

From the project root directory:

```bash
# Set your container registry
export REGISTRY=quay.io/your-org  # or docker.io/your-username, ghcr.io/your-org

# Build images
docker build -t $REGISTRY/ai-reviewer-api:latest -f Dockerfile .
docker build -t $REGISTRY/ai-reviewer-frontend:latest -f frontend/Dockerfile frontend/

# Push to registry
docker push $REGISTRY/ai-reviewer-api:latest
docker push $REGISTRY/ai-reviewer-frontend:latest

# Update manifests to use your images
cd k8s
sed -i.bak "s|image: ai-reviewer-api:latest|image: $REGISTRY/ai-reviewer-api:latest|" api.yaml
sed -i.bak "s|image: ai-reviewer-frontend:latest|image: $REGISTRY/ai-reviewer-frontend:latest|" frontend.yaml
```

### 2. Configure Environment Variables

```bash
# Copy template and edit with your API keys
cp env.template .env
# Edit .env with your OpenAI key, database password, etc.
```

### 3. Deploy to Cluster

**OpenShift:**
```bash
oc create namespace ai-reviewer
oc create secret generic app-secrets --from-env-file=.env -n ai-reviewer
oc apply -f . -n ai-reviewer

# Get the URL
oc get routes -n ai-reviewer
```

**Vanilla Kubernetes:**
```bash
kubectl create namespace ai-reviewer
kubectl create secret generic app-secrets --from-env-file=.env -n ai-reviewer

# Apply all manifests (OpenShift Routes will be ignored)
kubectl apply -f configmap.yaml -f database.yaml -f api.yaml -f frontend.yaml -n ai-reviewer
> If you want to run docling, run -f docling.yaml

# Access via port-forward
kubectl port-forward -n ai-reviewer svc/frontend 3000:3000
# Visit http://localhost:3000
```

## Platform-Specific Notes

### OpenShift
- Routes are automatically created for external access
- Network policies work out of the box
- Default storage class is used automatically
- No additional configuration needed

### AWS EKS
```bash
# Optional: Use specific storage class
sed -i 's|# storageClassName: ""|storageClassName: "gp3"|' database.yaml api.yaml
```

### Google GKE
```bash
# Optional: Use specific storage class
sed -i 's|# storageClassName: ""|storageClassName: "standard"|' database.yaml api.yaml
```

### Vanilla Kubernetes with Ingress
Save this as `ingress.yaml` and apply separately:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ai-reviewer
spec:
  ingressClassName: nginx
  rules:
  - host: ai-reviewer.yourdomain.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service: {name: api, port: {number: 8000}}
      - path: /
        pathType: Prefix
        backend:
          service: {name: frontend, port: {number: 3000}}
```

## Common Operations

**View logs:**
```bash
kubectl logs -f deployment/api -n ai-reviewer
kubectl logs -f deployment/frontend -n ai-reviewer
kubectl logs -f deployment/docling-serve -n ai-reviewer
```

**Check status:**
```bash
kubectl get pods -n ai-reviewer
kubectl get all -n ai-reviewer
```

**Update environment variables:**
```bash
kubectl create secret generic app-secrets --from-env-file=.env \
  --dry-run=client -o yaml -n ai-reviewer | kubectl apply -f -
kubectl rollout restart deployment/api -n ai-reviewer
```

**Database backup:**
```bash
kubectl exec deployment/db -n ai-reviewer -- \
  pg_dump -U ai_reviewer_user ai_reviewer > backup-$(date +%Y%m%d).sql
```

## Optional: Network Security

For production, apply network policies to restrict pod-to-pod traffic:
```bash
kubectl apply -f network-policy.yaml -n ai-reviewer
```

**Note:** Requires a CNI plugin that supports NetworkPolicy (Calico, Cilium, Weave).  
OpenShift has this by default.

## Troubleshooting

**Pods not starting:**
```bash
kubectl describe pod -l app=api -n ai-reviewer
kubectl logs -l app=api -n ai-reviewer
```

**Image pull errors:**
```bash
# Verify image names in manifests match your registry
grep "image:" api.yaml frontend.yaml

# For private registries, create image pull secret
kubectl create secret docker-registry regcred \
  --docker-server=your-registry.io \
  --docker-username=your-username \
  --docker-password=your-password \
  -n ai-reviewer
  
# Add to deployments under spec.template.spec:
#   imagePullSecrets:
#   - name: regcred
```

**Database connection issues:**
```bash
kubectl logs deployment/api -n ai-reviewer | grep -i database
kubectl exec -it deployment/db -n ai-reviewer -- psql -U ai_reviewer_user -d ai_reviewer
```

## What's Deployed

| Component | Description | Port |
|-----------|-------------|------|
| **frontend** | Next.js UI | 3000 |
| **api** | FastAPI backend with auto-migrations | 8000 |
| **db** | PostgreSQL 16 + pgvector | 5432 |
| **docling-serve** | Document conversion service (optional) | 5001 |

**Persistent Storage:**
- Database data: 20Gi
- API uploads: 20Gi

## Docling-serve (Document Conversion)

Docling-serve provides advanced document conversion (PDF, DOCX, etc.) with OCR and table extraction.

**Enabling Docling:**

1. Add `DOCLING_SERVE_API_KEY` to your `.env` file (or app-secrets)
2. Update `api-config` ConfigMap to set `FILE_CONVERTER: "docling"`:
   ```bash
   kubectl edit configmap api-config -n ai-reviewer
   # Change FILE_CONVERTER from "markitdown" to "docling"
   ```
3. Restart the API deployment:
   ```bash
   kubectl rollout restart deployment/api -n ai-reviewer
   ```

**Note:** Docling-serve requires more resources (1-4GB RAM). For production, consider scaling resources in `docling.yaml`.

## Clean Up

Remove everything:
```bash
kubectl delete namespace ai-reviewer
```

