================================================================================
🔍 GITHUB ACTIONS WORKFLOWS ANALYSIS
================================================================================

✅ WORKFLOWS THAT WILL RUN (GitHub-hosted runners)
--------------------------------------------------------------------------------

📄 AMD64 Python Package
   File: amd64-python-package.yml
   Triggers: push, pull_request
   Jobs (3):
     - build: ubuntu-latest
     - integration-tests: ubuntu-latest
     - docker-build: ubuntu-latest

📄 AMD64 Release Pipeline
   File: amd64-release.yml
   Triggers: push, workflow_dispatch
   Jobs (8):
     - validate-amd64-release: ubuntu-latest
     - amd64-build-test: ubuntu-latest
     - amd64-build-packages: ubuntu-latest
     - amd64-docker-build: ubuntu-latest
     - amd64-docker-gpu-build: ubuntu-latest
     - amd64-publish-pypi: ubuntu-latest
     - amd64-create-release: ubuntu-latest
     - amd64-notify-completion: ubuntu-latest

📄 MCP Blue/Green CI/CD Pipeline
   File: blue_green_pipeline.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (4):
     - test: ubuntu-20.04
     - build: ubuntu-20.04
     - deploy: ubuntu-20.04
     - monitor: ubuntu-20.04

📄 Cluster Services Tests
   File: cluster-tests.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (6):
     - cluster-unit-tests: ubuntu-20.04
     - vfs-integration-tests: ubuntu-20.04
     - http-api-integration-tests: ubuntu-20.04
     - integration-tests: ubuntu-20.04
     - performance-tests: ubuntu-20.04
     - test-summary: ubuntu-20.04

📄 Test Coverage
   File: coverage.yml
   Triggers: push, pull_request
   Jobs (1):
     - coverage: ubuntu-20.04

📄 Daemon Configuration Tests (Clean)
   File: daemon-config-tests-clean.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (4):
     - test-daemon-config: ubuntu-20.04
     - test-installer-config-integration: ubuntu-20.04
     - test-s3-config: ubuntu-20.04
     - test-comprehensive-config: ubuntu-20.04

📄 Daemon Configuration Tests
   File: daemon-config-tests-simple.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (4):
     - test-daemon-config: ubuntu-20.04
     - test-installer-config-integration: ubuntu-20.04
     - test-service-specific-config: ubuntu-20.04
     - report: ubuntu-20.04

📄 Daemon Configuration Tests
   File: daemon-config-tests.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (4):
     - test-daemon-config: ubuntu-20.04
     - test-installer-config-integration: ubuntu-latest
     - test-service-specific-config: ubuntu-latest
     - report: ubuntu-latest

📄 Daemon Tests and Health Checks
   File: daemon-tests.yml
   Triggers: push, pull_request, schedule
   Jobs (6):
     - daemon-unit-tests: ubuntu-latest
     - daemon-performance-tests: ubuntu-latest
     - daemon-docker-tests: ubuntu-latest
     - daemon-cluster-tests: ubuntu-latest
     - daemon-stress-tests: ubuntu-latest
     - notify-on-failure: ubuntu-latest

📄 Dependency Management
   File: dependencies.yml
   Triggers: schedule, workflow_dispatch
   Jobs (1):
     - check-dependencies: ubuntu-20.04

📄 Deploy
   File: deploy.yml
   Triggers: workflow_dispatch
   Jobs (1):
     - deploy: ubuntu-20.04

📄 Build and Publish Docker Image
   File: docker-build.yml
   Triggers: push, pull_request
   Jobs (2):
     - build: ubuntu-20.04
     - publish-helm: ubuntu-20.04

📄 Docker CI/CD
   File: docker.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (5):
     - docker-lint: ubuntu-20.04
     - build-and-test: ubuntu-20.04
     - publish: ubuntu-20.04
     - helm-lint: ubuntu-20.04
     - deploy-to-staging: ubuntu-20.04

📄 Documentation
   File: docs.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (2):
     - build-docs: ubuntu-20.04
     - deploy-docs: ubuntu-20.04

📄 IPFS-Kit Enhanced CI/CD Pipeline
   File: enhanced-ci-cd.yml
   Triggers: push, pull_request
   Jobs (9):
     - lint-and-security: ubuntu-latest
     - test: ubuntu-latest
     - docker-build: ubuntu-latest
     - integration-test: ubuntu-latest
     - performance-test: ubuntu-latest
     - security-scan: ubuntu-latest
     - release: ubuntu-latest
     - deploy: ubuntu-latest
     - cleanup: ubuntu-latest

📄 Enhanced MCP Server CI/CD
   File: enhanced-mcp-server.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (5):
     - test-enhanced-mcp-server: ubuntu-20.04
     - test-configuration-management: ubuntu-20.04
     - integration-test: ubuntu-20.04
     - docker-test: ubuntu-20.04
     - report: ubuntu-20.04

📄 Final MCP Server CI/CD
   File: final-mcp-server.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (5):
     - test-server: ubuntu-20.04
     - docker-test: ubuntu-20.04
     - docker-compose-test: ubuntu-20.04
     - integration-test: ubuntu-20.04
     - publish-docker: ubuntu-20.04

📄 Full CI/CD Pipeline with Enhanced Features
   File: full-pipeline.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (5):
     - basic-tests: 
     - configuration-tests: 
     - mcp-server-tests: 
     - package-tests: 
     - integration-summary: ubuntu-20.04

📄 Lint and Type Check
   File: lint.yml
   Triggers: push, pull_request
   Jobs (1):
     - lint: ubuntu-20.04

📄 Multi-Architecture Build
   File: multi-arch-build.yml
   Triggers: push, pull_request, release
   Jobs (5):
     - test-amd64: ubuntu-latest
     - test-arm64: ubuntu-latest
     - build-multi-arch: ubuntu-latest
     - security-scan: ubuntu-latest
     - performance-benchmarks: ubuntu-latest

📄 GitHub Pages
   File: pages.yml
   Triggers: push, workflow_dispatch
   Jobs (1):
     - build: ubuntu-20.04

📄 Pre-Release Deprecation Check
   File: pre_release_deprecation_check.yml
   Triggers: push, workflow_dispatch
   Jobs (1):
     - deprecation-guard: ubuntu-latest

📄 Python Package
   File: python-package.yml
   Triggers: push, pull_request
   Jobs (3):
     - test: ubuntu-20.04
     - build-and-publish: ubuntu-20.04
     - build-and-publish-testpypi: ubuntu-20.04

📄 Release Management
   File: release.yml
   Triggers: workflow_dispatch
   Jobs (1):
     - prepare-release: ubuntu-20.04

📄 Run Enhanced Tests
   File: run-tests-enhanced.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (3):
     - test: ubuntu-20.04
     - mcp-server-test: ubuntu-20.04
     - report: ubuntu-20.04

📄 Run Tests
   File: run-tests.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (2):
     - test: ubuntu-20.04
     - report: ubuntu-20.04

📄 Security Scanning
   File: security.yml
   Triggers: push, pull_request, schedule
   Jobs (3):
     - dependency-check: ubuntu-20.04
     - bandit-scan: ubuntu-20.04
     - docker-scan: ubuntu-20.04

📄 WebRTC Performance Benchmarking
   File: webrtc_benchmark.yml
   Triggers: push, pull_request, schedule, workflow_dispatch
   Jobs (2):
     - benchmark: ubuntu-20.04
     - update-baseline: ubuntu-20.04

📄 Python package
   File: workflow.yml
   Triggers: push, pull_request
   Jobs (5):
     - test: ubuntu-20.04
     - lint: ubuntu-20.04
     - build: ubuntu-20.04
     - publish-to-pypi: ubuntu-20.04
     - publish-to-testpypi: ubuntu-20.04


❌ WORKFLOWS THAT WON'T RUN (requires self-hosted runners)
--------------------------------------------------------------------------------

📄 AMD64 CI/CD Pipeline
   File: amd64-ci.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (2):
     - test-amd64: self-hosted, amd64
     - build-docker-amd64: self-hosted, amd64
   ⚠️  STATUS: Will be queued indefinitely (no runners available)

📄 ARM64 CI/CD Pipeline
   File: arm64-ci.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (2):
     - test-arm64: self-hosted, arm64, dgx
     - build-docker-arm64: self-hosted, arm64, dgx
   ⚠️  STATUS: Will be queued indefinitely (no runners available)


⚠️  WORKFLOWS WITH MIXED RUNNERS
--------------------------------------------------------------------------------

📄 GPU Testing Pipeline
   File: gpu-testing.yml
   Triggers: push, pull_request, schedule, workflow_dispatch
   Jobs (5):
     ✅ Will run - detect-changes: ubuntu-latest
     ❌ Won't run - gpu-tests: self-hosted, gpu, nvidia
     ❌ Won't run - docker-gpu-tests: self-hosted, gpu, nvidia
     ❌ Won't run - memory-leak-tests: self-hosted, gpu, nvidia
     ✅ Will run - report-results: ubuntu-latest

📄 Multi-Architecture CI/CD
   File: multi-arch-ci.yml
   Triggers: push, pull_request, workflow_dispatch
   Jobs (6):
     ✅ Will run - test-multi-arch: ubuntu-latest
     ❌ Won't run - test-arm64-native: self-hosted, ARM64
     ❌ Won't run - test-amd64-native: self-hosted, amd64
     ✅ Will run - test-riscv: ubuntu-latest
     ✅ Will run - verify-dependencies: ubuntu-latest
     ✅ Will run - test-summary: ubuntu-latest

📄 Publish Python Package
   File: publish-package.yml
   Triggers: release, workflow_dispatch
   Jobs (5):
     ✅ Will run - build: ubuntu-latest
     ✅ Will run - test-install: ${{ matrix.os }}
     ✅ Will run - publish-test-pypi: ubuntu-latest
     ✅ Will run - publish-pypi: ubuntu-latest
     ✅ Will run - create-github-release: ubuntu-latest


================================================================================
📊 SUMMARY
================================================================================
Total workflows: 34
  ✅ Fully functional (GitHub-hosted): 29
  ❌ Blocked (self-hosted only): 2
  ⚠️  Partially working (mixed): 3
  🚫 Disabled: 0

💡 RECOMMENDATION:
   You have workflows configured for self-hosted runners that won't run.
   Options:
   1. Set up self-hosted runners (use ./scripts/setup-github-runner.sh)
   2. Convert workflows to use GitHub-hosted runners (ubuntu-latest)
   3. Disable/delete workflows you don't need
================================================================================
