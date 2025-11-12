# Environment variables that assist in troubleshooting

The following environment variables may be useful for troubleshooting:

```text
  EG_DOCKER_LOG_LEVEL=WARNING
    By default, the docker client library is too verbose for its logging.  This
    value can be adjusted in situations where docker troubleshooting may be warranted.

  EG_KUBERNETES_LOG_LEVEL=WARNING
    By default, the kubernetes client library is too verbose for its logging.  This
    value can be adjusted in situations where kubernetes troubleshooting may be
    warranted.

  EG_LOG_LEVEL=10
    Used by remote launchers and gateway listeners (where the kernel runs), this
    indicates the level of logging used by those entities.  Level 10 (DEBUG) is
    recommended since they don't do verbose logging.

  EG_MAX_POLL_ATTEMPTS=10
    Polling is used in various places during life-cycle management operations - like
    determining if a kernel process is still alive, stopping the process, waiting
    for the process to terminate, etc.  As a result, it may be useful to adjust
    this value during those kinds of troubleshooting scenarios, although that
    should rarely be necessary.

  EG_POLL_INTERVAL=0.5
    The interval (in seconds) to wait before checking poll results again.

  EG_RESTART_STATUS_POLL_INTERVAL=1.0
    The interval (in seconds) to wait before polling for the restart status again when
    duplicate restart request for the same kernel is received or when a shutdown request
    is received while kernel is still restarting.

  EG_REMOVE_CONTAINER=True
    Used by launch_docker.py, indicates whether the kernel's docker container should be
    removed following its shutdown.  Set this value to 'False' if you want the container
    to be left around in order to troubleshoot issues.  Remember to set back to 'True'
    to restore normal operation.

  EG_SOCKET_TIMEOUT=5.0
    The time (in seconds) the enterprise gateway will wait on its connection
    file socket waiting on return from a remote kernel launcher.  Upon timeout, the
    operation will be retried immediately, until the overall time limit has been
    exceeded.

  EG_SSH_LOG_LEVEL=WARNING
    By default, the paramiko ssh library is too verbose for its logging.  This
    value can be adjusted in situations where ssh troubleshooting may be warranted.

  EG_YARN_LOG_LEVEL=WARNING
    By default, the yarn-api-client library is too verbose for its logging.  This
    value can be adjusted in situations where YARN troubleshooting may be warranted.
```
