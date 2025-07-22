
## Docker方式运行
```
# 构建镜像
docker build -t mcp-app .

# 删除旧容器
docker rm -f mymcp

# 运行容器
# 挂载目录 -v /share/CACHEDEV3_DATA/fs/App/Agent:/app
# 共享主机网络 --network host
docker run -d --name mymcp -v /share/CACHEDEV3_DATA/fs/App/Agent:/app --restart always --network host mcp-app

```