# mcp-prometheus-srv
MCP server to allow LLM to review k8s metrics in prometheus

http://mcp-monitor.apexkube.xyz

kubectl -n monitoring port-forward service/prometheus-server 9090:80

kubectl -n woodez-database port-forward service/postgres-svc 5432:5432

https://github.com/woodez-kubernetes/mcp-prometheus-srv.git