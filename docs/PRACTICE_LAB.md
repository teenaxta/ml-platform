# Practice Lab Guide Set

This repository now has two practice lab paths instead of one mixed workflow.

- Start with [PRACTICE_LAB_FOUNDATIONS.md](./PRACTICE_LAB_FOUNDATIONS.md). It explains the shared concepts, platform architecture, CI/CD model, container and registry basics, and the rules that apply to both labs.
- Continue with [PRACTICE_LAB_1_PRODUCTION.md](./PRACTICE_LAB_1_PRODUCTION.md) if you want the advanced, production-style workflow with strict repository boundaries.
- Continue with [PRACTICE_LAB_2_REPO_NATIVE.md](./PRACTICE_LAB_2_REPO_NATIVE.md) if you want the simpler operational path where the learner works directly in this `ml-platform` repository.
- Use [JUPYTERHUB_GUIDE.md](./JUPYTERHUB_GUIDE.md) whenever you need to understand notebook environment setup, Spark-related configuration, package management, and safe usage patterns in JupyterHub.

## Which guide should you choose?

Choose Lab 1 when you want to learn how teams usually operate in production:

- infrastructure code is protected
- runtime containers are not edited interactively
- code is delivered through Git, CI/CD, images, and controlled deployments
- dbt, feature definitions, training logic, and orchestration are usually split by repository or by strict internal boundaries

Choose Lab 2 when you want a simpler learning path:

- you are still expected to work through Git and CI/CD
- you still must not use `docker exec`
- you are allowed to make student changes directly inside this repository
- the workflow is easier because the repository already contains the platform reference implementation

## Recommended reading order

1. [GETTING_STARTED.md](../GETTING_STARTED.md)
2. [ACCESS_AND_URLS.md](./ACCESS_AND_URLS.md)
3. [PRACTICE_LAB_FOUNDATIONS.md](./PRACTICE_LAB_FOUNDATIONS.md)
4. One of the two lab guides
5. [JUPYTERHUB_GUIDE.md](./JUPYTERHUB_GUIDE.md) when you begin notebook-based work

## Why the guide set was split

The earlier lab guide tried to teach production practices and beginner learning steps in one document. That made the workflow harder to follow because:

- shared concepts were repeated or implied instead of explained once
- production constraints and simplified learning shortcuts were mixed together
- beginners had to infer why a tool existed before they knew how to use it

The new structure separates:

- shared foundations
- strict production operating model
- simpler repository-native operating model
- JupyterHub environment management

That separation makes it easier to teach both the "why" and the "how" without hiding engineering constraints.
