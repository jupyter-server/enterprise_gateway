# JEGgernaut: Experimental Scheduler for Jupyter Enterprise Gateway

JEGgernaut is an experimental fork of [Jupyter Enterprise Gateway (JEG)](https://github.com/jupyter/enterprise_gateway),
created to explore and evaluate different kernel scheduling strategies - including
**Round Robin (RR)**, **Least Connection (LC)**, and **First Come First Serve (FCFS)**.

## Project Goals

- Exploring the performance impact of alternative scheduling algorithms.
- Compare resource fairness and latency between strategies.
- Provide experimental insights for future scalability improvements in JEG.

## Algorithms Under Study

| Scheduler | Description |
|------------|-------------|
| **Round Robin** | Distributes workloads evenly in a rotating order. |
| **Least Connection** | Assigns kernels to the gateway node with the fewest active connections. |
| **FCFS (First Come First Serve)** | Assigns tasks in strict arrival order. |

Round Robin and Least Connection are the default algorithms of Jupyter Enterprise Gateway (JEG).