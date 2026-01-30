# CI/CD Pipeline Setup for IPFS Kit

This guide provides comprehensive instructions for setting up Continuous Integration and Continuous Deployment (CI/CD) pipelines for IPFS Kit. It covers various CI/CD platforms, automation strategies, and best practices.

## Table of Contents

1. [Introduction](#introduction)
2. [GitHub Actions](#github-actions)
   - [Testing Workflow](#testing-workflow)
   - [Linting and Type Checking](#linting-and-type-checking)
   - [Build and Publish Workflow](#build-and-publish-workflow)
   - [Docker Image Workflow](#docker-image-workflow)
   - [Documentation Updates](#documentation-updates)
3. [GitLab CI/CD](#gitlab-cicd)
   - [GitLab Pipeline Configuration](#gitlab-pipeline-configuration)
   - [GitLab Container Registry](#gitlab-container-registry)
4. [Jenkins](#jenkins)
   - [Jenkinsfile for IPFS Kit](#jenkinsfile-for-ipfs-kit)
   - [Jenkins Pipeline Stages](#jenkins-pipeline-stages)
5. [CircleCI](#circleci)
   - [CircleCI Configuration](#circleci-configuration)
6. [Testing Strategies](#testing-strategies)
   - [Matrix Testing](#matrix-testing)
   - [Test Coverage Reports](#test-coverage-reports)
   - [Parallel Testing](#parallel-testing)
7. [Code Quality and Security](#code-quality-and-security)
   - [Code Quality Checks](#code-quality-checks)
   - [Security Scanning](#security-scanning)
   - [Dependency Validation](#dependency-validation)
8. [Deployment Automation](#deployment-automation)
   - [Environment Configuration](#environment-configuration)
   - [Rolling Updates](#rolling-updates)
   - [Canary Deployments](#canary-deployments)
9. [Monitoring and Alerting](#monitoring-and-alerting)
   - [Pipeline Monitoring](#pipeline-monitoring)
   - [Deployment Verification](#deployment-verification)
10. [Best Practices](#best-practices)
    - [Pipeline Optimization](#pipeline-optimization)
    - [Secret Management](#secret-management)
    - [Pipeline Documentation](#pipeline-documentation)

## Introduction

A CI/CD pipeline automates the process of testing, building, and deploying software updates, ensuring code quality and reducing manual intervention. For IPFS Kit, the CI/CD pipeline should handle:

1. **Code Quality Verification**: Run linting and type checking
2. **Testing**: Execute unit, integration, and performance tests
3. **Building**: Create Python packages and Docker images
4. **Publishing**: Upload packages to PyPI and container registries
5. **Deployment**: Deploy to development, staging, and production environments

The pipeline should execute on every code push and pull request, with deployment steps running only on specific branches or tags.

## GitHub Actions

GitHub Actions is a convenient CI/CD solution for projects hosted on GitHub. Here are configuration files for various workflows:

### Testing Workflow

Create `.github/workflows/test.yml`:

```yaml
name: Run Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.8', '3.9', '3.10', '3.11', '3.12']

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
    
    - name: Run tests
      run: |
        python -m pytest test/ --cov=ipfs_kit_py --cov-report=xml
    
    - name: Upload coverage report
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: false
        verbose: true
```

### Linting and Type Checking

Create `.github/workflows/lint.yml`:

```yaml
name: Lint and Type Check

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install black ruff mypy pylint
        pip install -e ".[dev]"
    
    - name: Check formatting with Black
      run: |
        black --check ipfs_kit_py test examples
    
    - name: Lint with Ruff
      run: |
        ruff check ipfs_kit_py test examples
    
    - name: Type check with MyPy
      run: |
        mypy ipfs_kit_py
    
    - name: Check for duplicated code
      run: |
        pylint --disable=all --enable=duplicate-code ipfs_kit_py
```

### Build and Publish Workflow

Create `.github/workflows/publish.yml`:

```yaml
name: Build and Publish

on:
  release:
    types: [created]

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install build dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine wheel
    
    - name: Build package
      run: |
        python -m build
    
    - name: Check package
      run: |
        twine check dist/*
    
    - name: Publish to Test PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        user: __token__
        password: ${{ secrets.TEST_PYPI_API_TOKEN }}
        repository-url: https://test.pypi.org/legacy/
        skip-existing: true
    
    - name: Test installation from Test PyPI
      run: |
        pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple ipfs_kit_py
        python -c "import ipfs_kit_py; print(ipfs_kit_py.__version__)"
    
    - name: Publish to PyPI
      if: startsWith(github.ref, 'refs/tags')
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        user: __token__
        password: ${{ secrets.PYPI_API_TOKEN }}
```

### Docker Image Workflow

Create `.github/workflows/docker.yml`:

```yaml
name: Build and Push Docker Image

on:
  release:
    types: [created]
  push:
    branches: [ main, develop ]
    paths:
      - 'Dockerfile'
      - 'docker/**'
      - 'ipfs_kit_py/**'

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up QEMU
      uses: docker/setup-qemu-action@v2
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
    
    - name: Login to DockerHub
      uses: docker/login-action@v2
      with:
        username: ${{ secrets.DOCKERHUB_USERNAME }}
        password: ${{ secrets.DOCKERHUB_TOKEN }}
    
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v4
      with:
        images: username/ipfs-kit
        tags: |
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}
          type=ref,event=branch
    
    - name: Build and push
      uses: docker/build-push-action@v4
      with:
        context: .
        platforms: linux/amd64,linux/arm64
        push: ${{ github.event_name != 'pull_request' }}
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
```

### Documentation Updates

Create `.github/workflows/docs.yml`:

```yaml
name: Update Documentation

on:
  push:
    branches: [ main ]
    paths:
      - 'docs/**'
      - 'README.md'
      - 'ipfs_kit_py/**/*.py'

jobs:
  documentation:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[docs]"
    
    - name: Build documentation
      run: |
        sphinx-build -b html docs/source docs/build
    
    - name: Deploy to GitHub Pages
      uses: peaceiris/actions-gh-pages@v3
      if: github.ref == 'refs/heads/main'
      with:
        github_token: ${{ secrets.GITHUB_TOKEN }}
        publish_dir: ./docs/build
```

## GitLab CI/CD

If you're using GitLab, create a `.gitlab-ci.yml` file:

### GitLab Pipeline Configuration

```yaml
stages:
  - test
  - build
  - publish
  - deploy

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.pip-cache"
  DOCKER_TLS_CERTDIR: "/certs"

cache:
  paths:
    - .pip-cache/
    - venv/

# Templates
.python-job:
  image: python:3.11-slim
  before_script:
    - python -V
    - pip install virtualenv
    - virtualenv venv
    - source venv/bin/activate
    - pip install -e ".[dev]"

# Testing jobs
test:lint:
  extends: .python-job
  stage: test
  script:
    - pip install black ruff mypy pylint
    - black --check ipfs_kit_py test examples
    - ruff check ipfs_kit_py test examples
    - mypy ipfs_kit_py
    - pylint --disable=all --enable=duplicate-code ipfs_kit_py

test:pytest:
  extends: .python-job
  stage: test
  script:
    - python -m pytest test/ --cov=ipfs_kit_py --cov-report=xml
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

# Build jobs
build:package:
  extends: .python-job
  stage: build
  script:
    - pip install build twine wheel
    - python -m build
    - twine check dist/*
  artifacts:
    paths:
      - dist/
    expire_in: 1 week

build:docker:
  image: docker:20.10.16
  stage: build
  services:
    - docker:20.10.16-dind
  before_script:
    - docker info
  script:
    - |
      if [[ "$CI_COMMIT_BRANCH" == "main" ]]; then
        docker build -t $CI_REGISTRY_IMAGE:latest .
        docker tag $CI_REGISTRY_IMAGE:latest $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
      elif [[ "$CI_COMMIT_BRANCH" == "develop" ]]; then
        docker build -t $CI_REGISTRY_IMAGE:develop .
        docker tag $CI_REGISTRY_IMAGE:develop $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
      elif [[ "$CI_COMMIT_TAG" ]]; then
        docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_TAG .
        docker tag $CI_REGISTRY_IMAGE:$CI_COMMIT_TAG $CI_REGISTRY_IMAGE:latest
      else
        docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_REF_SLUG .
      fi
  rules:
    - if: $CI_COMMIT_BRANCH == "main" || $CI_COMMIT_BRANCH == "develop" || $CI_COMMIT_TAG
      changes:
        - Dockerfile
        - docker/**/*
        - ipfs_kit_py/**/*

# Publish jobs
publish:pypi:
  extends: .python-job
  stage: publish
  script:
    - pip install twine
    - twine upload dist/* --repository-url https://test.pypi.org/legacy/ --username __token__ --password ${TEST_PYPI_API_TOKEN}
    - |
      if [[ "$CI_COMMIT_TAG" ]]; then
        twine upload dist/* --username __token__ --password ${PYPI_API_TOKEN}
      fi
  rules:
    - if: $CI_COMMIT_TAG

publish:docker:
  image: docker:20.10.16
  stage: publish
  services:
    - docker:20.10.16-dind
  before_script:
    - docker info
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - |
      if [[ "$CI_COMMIT_BRANCH" == "main" ]]; then
        docker push $CI_REGISTRY_IMAGE:latest
        docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
      elif [[ "$CI_COMMIT_BRANCH" == "develop" ]]; then
        docker push $CI_REGISTRY_IMAGE:develop
        docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
      elif [[ "$CI_COMMIT_TAG" ]]; then
        docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_TAG
        docker push $CI_REGISTRY_IMAGE:latest
      else
        docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_REF_SLUG
      fi
  rules:
    - if: $CI_COMMIT_BRANCH == "main" || $CI_COMMIT_BRANCH == "develop" || $CI_COMMIT_TAG
      changes:
        - Dockerfile
        - docker/**/*
        - ipfs_kit_py/**/*

# Deployment jobs
deploy:staging:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache curl
  script:
    - curl -X POST ${STAGING_DEPLOY_WEBHOOK} -H "Content-Type: application/json" -d "{\"image\": \"${CI_REGISTRY_IMAGE}:${CI_COMMIT_SHA}\"}"
  environment:
    name: staging
  rules:
    - if: $CI_COMMIT_BRANCH == "develop"

deploy:production:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache curl
  script:
    - curl -X POST ${PRODUCTION_DEPLOY_WEBHOOK} -H "Content-Type: application/json" -d "{\"image\": \"${CI_REGISTRY_IMAGE}:${CI_COMMIT_TAG}\"}"
  environment:
    name: production
  rules:
    - if: $CI_COMMIT_TAG
```

### GitLab Container Registry

To use GitLab's container registry, make sure to:

1. Configure variables:
   - `CI_REGISTRY`: GitLab's container registry URL
   - `CI_REGISTRY_USER`: Username for registry access
   - `CI_REGISTRY_PASSWORD`: Password or token for registry access

2. Enable the Container Registry for your project in GitLab settings

## Jenkins

For Jenkins CI, create a `Jenkinsfile` at the root of your repository:

### Jenkinsfile for IPFS Kit

```groovy
pipeline {
    agent none
    
    stages {
        stage('Test') {
            parallel {
                stage('Lint and Type Check') {
                    agent {
                        docker {
                            image 'python:3.11-slim'
                        }
                    }
                    steps {
                        sh '''
                            python -m pip install --upgrade pip
                            pip install black ruff mypy pylint
                            pip install -e ".[dev]"
                            black --check ipfs_kit_py test examples
                            ruff check ipfs_kit_py test examples
                            mypy ipfs_kit_py
                            pylint --disable=all --enable=duplicate-code ipfs_kit_py
                        '''
                    }
                }
                
                stage('Run Tests') {
                    agent {
                        docker {
                            image 'python:${PYTHON_VERSION}-slim'
                            args '-v ${WORKSPACE}:/app'
                        }
                    }
                    steps {
                        sh '''
                            python -m pip install --upgrade pip
                            pip install -e ".[dev]"
                            python -m pytest test/ --cov=ipfs_kit_py --cov-report=xml
                        '''
                    }
                    post {
                        always {
                            junit 'test-results.xml'
                            cobertura coberturaReportFile: 'coverage.xml'
                        }
                    }
                }
            }
        }
        
        stage('Build') {
            agent {
                docker {
                    image 'python:3.11-slim'
                }
            }
            steps {
                sh '''
                    python -m pip install --upgrade pip
                    pip install build twine wheel
                    python -m build
                    twine check dist/*
                '''
                stash includes: 'dist/**', name: 'dist'
            }
        }
        
        stage('Build Docker Image') {
            agent {
                docker {
                    image 'docker:20.10.16'
                    args '-v /var/run/docker.sock:/var/run/docker.sock'
                }
            }
            steps {
                script {
                    def imageTag = ''
                    if (env.BRANCH_NAME == 'main') {
                        imageTag = 'latest'
                    } else if (env.BRANCH_NAME == 'develop') {
                        imageTag = 'develop'
                    } else if (env.TAG_NAME) {
                        imageTag = env.TAG_NAME
                    } else {
                        imageTag = env.BRANCH_NAME.replaceAll('/', '-')
                    }
                    
                    docker.build("ipfs-kit:${imageTag}")
                }
            }
        }
        
        stage('Publish Package') {
            agent {
                docker {
                    image 'python:3.11-slim'
                }
            }
            when {
                expression { return env.TAG_NAME != null }
            }
            steps {
                unstash 'dist'
                withCredentials([string(credentialsId: 'pypi-token', variable: 'PYPI_TOKEN')]) {
                    sh '''
                        python -m pip install --upgrade pip
                        pip install twine
                        twine upload dist/* --username __token__ --password $PYPI_TOKEN
                    '''
                }
            }
        }
        
        stage('Publish Docker Image') {
            agent {
                docker {
                    image 'docker:20.10.16'
                    args '-v /var/run/docker.sock:/var/run/docker.sock'
                }
            }
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                    expression { return env.TAG_NAME != null }
                }
            }
            steps {
                script {
                    def imageTag = ''
                    if (env.BRANCH_NAME == 'main') {
                        imageTag = 'latest'
                    } else if (env.BRANCH_NAME == 'develop') {
                        imageTag = 'develop'
                    } else if (env.TAG_NAME) {
                        imageTag = env.TAG_NAME
                    }
                    
                    withCredentials([usernamePassword(credentialsId: 'docker-hub', passwordVariable: 'DOCKER_PASSWORD', usernameVariable: 'DOCKER_USERNAME')]) {
                        sh '''
                            echo $DOCKER_PASSWORD | docker login -u $DOCKER_USERNAME --password-stdin
                            docker tag ipfs-kit:${imageTag} $DOCKER_USERNAME/ipfs-kit:${imageTag}
                            docker push $DOCKER_USERNAME/ipfs-kit:${imageTag}
                        '''
                    }
                }
            }
        }
        
        stage('Deploy to Staging') {
            agent {
                label 'deploy'
            }
            when {
                branch 'develop'
            }
            steps {
                sh './deploy/deploy_staging.sh'
            }
        }
        
        stage('Deploy to Production') {
            agent {
                label 'deploy'
            }
            when {
                expression { return env.TAG_NAME != null }
            }
            steps {
                sh './deploy/deploy_production.sh'
            }
        }
    }
    
    post {
        always {
            echo 'Pipeline completed'
        }
        success {
            echo 'Pipeline succeeded!'
        }
        failure {
            echo 'Pipeline failed!'
        }
    }
}
```

### Jenkins Pipeline Stages

The Jenkins pipeline includes the following stages:

1. **Test**: Run linting, type checking, and tests in parallel
2. **Build**: Build the Python package and Docker image
3. **Publish**: Publish the package to PyPI and Docker image to registry
4. **Deploy**: Deploy to staging or production environments

## CircleCI

For CircleCI, create a `.circleci/config.yml` file:

### CircleCI Configuration

```yaml
version: 2.1

orbs:
  python: circleci/python@2.0.3
  docker: circleci/docker@2.2.0

commands:
  install-dependencies:
    steps:
      - python/install-packages:
          pkg-manager: pip
          packages:
            - -e ".[dev]"

jobs:
  lint:
    docker:
      - image: cimg/python:3.11
    steps:
      - checkout
      - python/install-packages:
          pkg-manager: pip
          packages:
            - black
            - ruff
            - mypy
            - pylint
      - run:
          name: Run linting
          command: |
            black --check ipfs_kit_py test examples
            ruff check ipfs_kit_py test examples
            mypy ipfs_kit_py
            pylint --disable=all --enable=duplicate-code ipfs_kit_py

  test:
    parameters:
      python-version:
        type: string
    docker:
      - image: cimg/python:<< parameters.python-version >>
    steps:
      - checkout
      - install-dependencies
      - run:
          name: Run tests
          command: |
            python -m pytest test/ --cov=ipfs_kit_py --cov-report=xml --junitxml=test-results/pytest.xml
      - store_test_results:
          path: test-results
      - store_artifacts:
          path: coverage.xml

  build:
    docker:
      - image: cimg/python:3.11
    steps:
      - checkout
      - python/install-packages:
          pkg-manager: pip
          packages:
            - build
            - twine
            - wheel
      - run:
          name: Build package
          command: |
            python -m build
            twine check dist/*
      - persist_to_workspace:
          root: .
          paths:
            - dist

  build-docker:
    machine:
      image: ubuntu-2204:current
    steps:
      - checkout
      - docker/check
      - docker/build:
          image: ipfs-kit
          tag: ${CIRCLE_SHA1}

  publish-package:
    docker:
      - image: cimg/python:3.11
    steps:
      - checkout
      - attach_workspace:
          at: .
      - run:
          name: Publish to Test PyPI
          command: |
            pip install twine
            twine upload dist/* --repository-url https://test.pypi.org/legacy/ --username __token__ --password ${TEST_PYPI_API_TOKEN}
      - run:
          name: Publish to PyPI
          command: |
            if [[ -n "$CIRCLE_TAG" ]]; then
              twine upload dist/* --username __token__ --password ${PYPI_API_TOKEN}
            fi

  publish-docker:
    machine:
      image: ubuntu-2204:current
    steps:
      - checkout
      - docker/check
      - docker/build:
          image: ipfs-kit
          tag: ${CIRCLE_SHA1}
      - docker/push:
          image: ipfs-kit
          tag: ${CIRCLE_SHA1}
      - run:
          name: Tag and push Docker image
          command: |
            if [[ "$CIRCLE_BRANCH" == "main" ]]; then
              docker tag ipfs-kit:${CIRCLE_SHA1} ${DOCKER_USERNAME}/ipfs-kit:latest
              docker push ${DOCKER_USERNAME}/ipfs-kit:latest
            elif [[ "$CIRCLE_BRANCH" == "develop" ]]; then
              docker tag ipfs-kit:${CIRCLE_SHA1} ${DOCKER_USERNAME}/ipfs-kit:develop
              docker push ${DOCKER_USERNAME}/ipfs-kit:develop
            elif [[ -n "$CIRCLE_TAG" ]]; then
              docker tag ipfs-kit:${CIRCLE_SHA1} ${DOCKER_USERNAME}/ipfs-kit:${CIRCLE_TAG}
              docker push ${DOCKER_USERNAME}/ipfs-kit:${CIRCLE_TAG}
              docker tag ipfs-kit:${CIRCLE_SHA1} ${DOCKER_USERNAME}/ipfs-kit:latest
              docker push ${DOCKER_USERNAME}/ipfs-kit:latest
            fi

workflows:
  version: 2
  build-test-publish:
    jobs:
      - lint
      - test:
          matrix:
            parameters:
              python-version: ["3.8", "3.9", "3.10", "3.11", "3.12"]
      - build:
          requires:
            - lint
            - test
      - build-docker:
          requires:
            - build
          filters:
            branches:
              only:
                - main
                - develop
            tags:
              only: /^v.*/
      - publish-package:
          requires:
            - build
          filters:
            branches:
              ignore: /.*/
            tags:
              only: /^v.*/
      - publish-docker:
          requires:
            - build-docker
          filters:
            branches:
              only:
                - main
                - develop
            tags:
              only: /^v.*/
```

## Testing Strategies

### Matrix Testing

Matrix testing involves running tests across multiple configurations, such as Python versions, operating systems, or dependency versions.

Example GitHub Actions matrix configuration:

```yaml
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.8', '3.9', '3.10', '3.11', '3.12']
        exclude:
          # Exclude specific combinations if needed
          - os: windows-latest
            python-version: '3.12'
      fail-fast: false  # Continue running other matrix jobs even if one fails
```

### Test Coverage Reports

Use coverage tools to track and improve test coverage:

1. **Generate coverage report**:
   ```bash
   python -m pytest --cov=ipfs_kit_py --cov-report=xml
   ```

2. **Upload to coverage services** (e.g., Codecov, Coveralls):
   ```yaml
   - uses: codecov/codecov-action@v3
     with:
       file: ./coverage.xml
   ```

3. **Set coverage thresholds**:
   ```bash
   python -m pytest --cov=ipfs_kit_py --cov-report=term --cov-fail-under=85
   ```

### Parallel Testing

Running tests in parallel can significantly reduce execution time:

1. **pytest-xdist**:
   ```bash
   python -m pytest -n auto  # Use all CPU cores
   ```

2. **Split by test types**:
   ```yaml
   jobs:
     test-unit:
       # Run unit tests
     test-integration:
       # Run integration tests
     test-performance:
       # Run performance tests
   ```

3. **CircleCI test splitting**:
   ```yaml
   - run:
       command: |
         python -m pytest --split-by=timings
   ```

## Code Quality and Security

### Code Quality Checks

Implement these code quality checks in your pipeline:

1. **Code formatting** with Black:
   ```bash
   black --check ipfs_kit_py test examples
   ```

2. **Linting** with Ruff:
   ```bash
   ruff check ipfs_kit_py test examples
   ```

3. **Type checking** with MyPy:
   ```bash
   mypy ipfs_kit_py
   ```

4. **Duplicate code detection** with Pylint:
   ```bash
   pylint --disable=all --enable=duplicate-code ipfs_kit_py
   ```

### Security Scanning

Add security scanning to identify vulnerabilities:

1. **Dependency scanning** with Safety:
   ```bash
   safety check
   ```

2. **SAST (Static Application Security Testing)** with Bandit:
   ```bash
   bandit -r ipfs_kit_py
   ```

3. **Container scanning** with Trivy:
   ```bash
   trivy image ipfs-kit:latest
   ```

### Dependency Validation

Validate dependencies for security and compatibility:

1. **Check for outdated packages**:
   ```bash
   pip list --outdated
   ```

2. **Verify dependency compatibility**:
   ```bash
   pip check
   ```

3. **Pin dependencies** in pyproject.toml or requirements.txt

## Deployment Automation

### Environment Configuration

Use environment-specific configurations:

1. **Environment variables**:
   - Development: `.env.dev`
   - Staging: `.env.staging`
   - Production: `.env.prod`

2. **Configuration files**:
   - Create templates for each environment
   - Substitute variables during deployment

3. **Secrets management**:
   - Use secure secret storage (e.g., HashiCorp Vault, AWS Secrets Manager)
   - Inject secrets during deployment

### GitOps Workflow

Implement GitOps for declarative infrastructure and deployments:

#### ArgoCD Integration

ArgoCD provides a GitOps continuous delivery tool for Kubernetes deployments:

```yaml
# Example ArgoCD Application for IPFS Kit
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ipfs-kit
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/yourusername/ipfs-kit-deployments.git
    targetRevision: HEAD
    path: deployments/k8s/environments/production
  destination:
    server: https://kubernetes.default.svc
    namespace: ipfs-kit-prod
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

#### Flux Integration

Flux provides another GitOps approach with automatic image updates:

```yaml
# Flux Kustomization for IPFS Kit
apiVersion: kustomize.toolkit.fluxcd.io/v1beta2
kind: Kustomization
metadata:
  name: ipfs-kit
  namespace: flux-system
spec:
  interval: 10m0s
  path: ./deployments/k8s/environments/production
  prune: true
  sourceRef:
    kind: GitRepository
    name: ipfs-kit-deployments
  healthChecks:
  - apiVersion: apps/v1
    kind: Deployment
    name: ipfs-worker
    namespace: ipfs-kit-prod
  timeout: 2m0s
```

```yaml
# Flux Image Update Automation
apiVersion: image.toolkit.fluxcd.io/v1beta1
kind: ImageUpdateAutomation
metadata:
  name: ipfs-kit-auto-update
  namespace: flux-system
spec:
  interval: 1m0s
  sourceRef:
    kind: GitRepository
    name: ipfs-kit-deployments
  git:
    checkout:
      ref:
        branch: main
    commit:
      author:
        email: fluxcdbot@users.noreply.github.com
        name: fluxcdbot
      messageTemplate: 'Update image to {{.NewDigest}}'
    push:
      branch: main
```

#### Jenkins X Integration

For a complete DevOps platform:

```yaml
# jenkins-x.yml
buildPack: python
pipelineConfig:
  pipelines:
    pullRequest:
      pipeline:
        stages:
        - name: build
          steps:
          - name: test
            command: python -m pytest test/
    release:
      pipeline:
        stages:
        - name: build
          steps:
          - name: build-package
            command: python -m build
          - name: publish
            command: twine upload dist/*
        - name: promote
          environment:
            - name: staging
            - name: production
```

### Rolling Updates

Implement rolling updates to minimize downtime:

1. **Kubernetes rolling update**:
   ```bash
   kubectl set image deployment/ipfs-worker ipfs-worker=ipfs-kit:new-version
   ```

2. **Health checks**:
   - Verify new instances are healthy before proceeding
   - Automatically rollback on failure

3. **Session draining**:
   - Allow existing operations to complete
   - Gradually redirect traffic to new instances

### Canary Deployments

Reduce risk with canary deployments:

1. **Deploy to subset of instances**:
   ```bash
   # Deploy to 10% of instances
   kubectl scale deployment ipfs-worker-canary --replicas=1
   kubectl scale deployment ipfs-worker --replicas=9
   ```

2. **Monitoring**:
   - Monitor error rates, latency, and resource usage
   - Automatically rollback if issues detected

3. **Gradual traffic shifting**:
   - Incrementally increase traffic to new version
   - Fully deploy after confidence is established

### GitHub Actions Deployment Example

Create a workflow for deploying to different environments:

```yaml
name: Deploy

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy to'
        required: true
        default: 'development'
        type: choice
        options:
        - development
        - staging
        - production

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment }}
    steps:
      - uses: actions/checkout@v3
      
      - name: Install kubectl
        uses: azure/setup-kubectl@v3
        
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-west-2
          
      - name: Update kubeconfig
        run: aws eks update-kubeconfig --name ipfs-cluster-${{ github.event.inputs.environment }}
      
      - name: Deploy to ${{ github.event.inputs.environment }}
        run: |
          # Set environment-specific variables
          if [ "${{ github.event.inputs.environment }}" == "production" ]; then
            REPLICAS_MASTER=2
            REPLICAS_WORKER=5
          elif [ "${{ github.event.inputs.environment }}" == "staging" ]; then
            REPLICAS_MASTER=1
            REPLICAS_WORKER=3
          else
            REPLICAS_MASTER=1
            REPLICAS_WORKER=1
          fi
          
          # Update kustomization file
          cat > deployments/k8s/environments/${{ github.event.inputs.environment }}/kustomization.yaml << EOF
          apiVersion: kustomize.config.k8s.io/v1beta1
          kind: Kustomization
          resources:
          - ../../base
          namespace: ipfs-kit-${{ github.event.inputs.environment }}
          patchesStrategicMerge:
          - patches/replicas.yaml
          images:
          - name: ipfs-kit
            newTag: ${GITHUB_SHA::8}
          EOF
          
          # Create patch for replicas
          mkdir -p deployments/k8s/environments/${{ github.event.inputs.environment }}/patches
          cat > deployments/k8s/environments/${{ github.event.inputs.environment }}/patches/replicas.yaml << EOF
          apiVersion: apps/v1
          kind: StatefulSet
          metadata:
            name: ipfs-master
          spec:
            replicas: ${REPLICAS_MASTER}
          ---
          apiVersion: apps/v1
          kind: Deployment
          metadata:
            name: ipfs-worker
          spec:
            replicas: ${REPLICAS_WORKER}
          EOF
          
          # Apply with kustomize
          kubectl apply -k deployments/k8s/environments/${{ github.event.inputs.environment }}
          
      - name: Verify deployment
        run: |
          kubectl -n ipfs-kit-${{ github.event.inputs.environment }} rollout status statefulset/ipfs-master --timeout=300s
          kubectl -n ipfs-kit-${{ github.event.inputs.environment }} rollout status deployment/ipfs-worker --timeout=300s
```

## Monitoring and Alerting

### Pipeline Monitoring

Monitor CI/CD pipeline health:

1. **Pipeline status dashboard**:
   - Show success/failure rates
   - Track execution time trends

2. **Notifications**:
   - Send alerts for failures via Slack, email, etc.
   - Include relevant logs and artifacts

3. **Pipeline metrics**:
   - Track build times
   - Monitor resource usage

### Deployment Verification

Verify deployments are successful:

1. **Smoke tests**:
   ```bash
   # Run basic API tests after deployment
   curl -f https://api.example.com/health
   ```

2. **Synthetic monitoring**:
   - Simulate user interactions
   - Verify critical functionality

3. **Metrics validation**:
   - Compare performance before and after deployment
   - Alert on degradation

## Best Practices

### Pipeline Optimization

Optimize your pipeline for speed and reliability:

1. **Caching**:
   - Cache dependencies
   - Cache build artifacts
   - Use layer caching for Docker builds

2. **Skip unnecessary steps**:
   - Only run affected tests on PRs
   - Skip deployment for documentation-only changes

3. **Parallel execution**:
   - Run independent steps in parallel
   - Use multiple executors

### Secret Management

Secure your secrets in CI/CD:

1. **Never commit secrets** to version control

2. **Use secret storage services**:
   - GitHub: Secrets or Dependabot secrets
   - GitLab: CI/CD Variables
   - Jenkins: Credentials Manager
   - CircleCI: Environment Variables or Contexts

3. **Rotate secrets regularly**:
   - Implement automatic rotation
   - Revoke compromised secrets immediately

### Pipeline Documentation

Document your CI/CD pipeline:

1. **Pipeline diagram**:
   - Visualize steps and dependencies
   - Show branch/tag conditions

2. **Runbook**:
   - Document common failure modes
   - Include troubleshooting steps

3. **Onboarding guide**:
   - Explain CI/CD setup for new team members
   - Document how to add new tests or deployment targets