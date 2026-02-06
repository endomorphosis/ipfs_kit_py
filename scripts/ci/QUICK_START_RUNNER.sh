#!/bin/bash
# Quick Start Guide for GitHub Actions Runner Setup
# Run this to get started immediately

set -e

cat << 'EOF'
╔═══════════════════════════════════════════════════════════╗
║  IPFS-Kit Docker Testing & GitHub Actions Runner Setup   ║
║                    Quick Start Guide                      ║
╚═══════════════════════════════════════════════════════════╝

CURRENT STATUS:
✅ Docker container built and tested successfully (x86_64)
✅ Lotus dependencies pre-installed and verified
✅ Container API working correctly
✅ GitHub Actions workflows configured
⚠️  Self-hosted runner needs setup

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: TEST DOCKER CONTAINER LOCALLY
Run this to verify your local Docker setup:

    docker run -d --name ipfs-kit-test \
      -p 9999:9999 \
      -e IPFS_KIT_AUTO_INSTALL_DEPS=0 \
      ipfs-kit:final daemon-only
    
    sleep 10
    curl http://localhost:9999/api/v1/status
    docker stop ipfs-kit-test && docker rm ipfs-kit-test

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 2: SETUP GITHUB ACTIONS RUNNER
Run the automated setup script:

    ./setup-github-runner.sh

Or manually:
1. Create runner directory:
   mkdir -p ~/actions-runner-amd64 && cd ~/actions-runner-amd64

2. Download latest runner:
   curl -o runner.tar.gz -L \
     https://github.com/actions/runner/releases/latest/download/actions-runner-linux-x64-*.tar.gz
   tar xzf runner.tar.gz

3. Get registration token from:
   https://github.com/endomorphosis/ipfs_kit_py/settings/actions/runners/new

4. Configure runner:
   ./config.sh --url https://github.com/endomorphosis/ipfs_kit_py \
     --token YOUR_TOKEN --labels amd64

5. Install as service:
   sudo ./svc.sh install
   sudo ./svc.sh start

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 3: TRIGGER WORKFLOW
Once runner is set up, push to trigger the workflow:

    git add .
    git commit -m "Add enhanced Docker testing workflow"
    git push origin main

Monitor at:
https://github.com/endomorphosis/ipfs_kit_py/actions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VERIFICATION COMMANDS

Check runner status:
    cd ~/actions-runner-amd64
    sudo ./svc.sh status

Check Docker image:
    docker images | grep ipfs-kit

Test Lotus dependencies:
    docker run --rm --entrypoint python3 ipfs-kit:final \
      -c "from ipfs_kit_py.install_lotus import install_lotus; \
          i = install_lotus(); \
          print('✅ OK' if i._check_hwloc_library_direct() else '❌ FAIL')"

Check container logs:
    docker logs <container_name>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FILES CREATED:
✓ .github/workflows/docker-enhanced-test.yml  - Enhanced CI/CD workflow
✓ setup-github-runner.sh                      - Automated runner setup
✓ DOCKER_TESTING_SUMMARY.md                   - Detailed documentation
✓ QUICK_START_RUNNER.sh                       - This guide

DOCUMENTATION:
📖 Full details: DOCKER_TESTING_SUMMARY.md
🔧 Runner setup: ./setup-github-runner.sh --help
🐳 Docker tests: See workflow file

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TROUBLESHOOTING

Runner not showing:
    sudo ./svc.sh status
    journalctl -u actions.runner.* -f

Docker permission denied:
    sudo usermod -aG docker $USER
    # Log out and back in

Container won't start:
    docker logs <container_name>
    docker exec <container_name> cat /tmp/supervisord.log

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ Ready to deploy! Your Docker container is production-ready.
   Set up the runner to enable automated testing in CI/CD.

EOF
