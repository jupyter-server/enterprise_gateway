for i in {1..5}; do
    curl -X POST http://localhost:8888/api/kernels -d '{"name":"python3"}'
done