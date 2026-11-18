// CSC418 DevOps for Cloud Computing - Lab Midterm
// Student: FA23-BDS-004   Job: MIDTERM-FA23-BDS-004
// GitHub push -> webhook -> retrain -> test -> deploy on EC2 -> push to Docker Hub -> email

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 20, unit: 'MINUTES')
    }

    triggers {
        githubPush()
        // Safety net if the webhook is ever unreachable; uncomment before grading:
        // pollSCM('H/2 * * * *')
    }

    environment {
        STUDENT_ID     = 'FA23-BDS-004'

        // ---- Docker Hub (field 7 on the Google Form) ----------------------
        IMAGE          = 'ateebakmal/midterm-fa23-bds-004'
        DOCKERHUB_CRED = 'dockerhub-creds-devops-mid-global'

        // ---- Deployment ----------------------------------------------------
        CONTAINER      = 'midterm-fa23-bds-004'
        HOST_PORT      = '8000'

        // ---- Notification --------------------------------------------------
        // From address comes from the global Extended E-mail config
        // (smtp.gmail.com:465, SSL, authenticated as ateebakmal009@gmail.com).
        // Build mail goes to the commit author only. To also notify the
        // instructor, add 'qasimalik@gmail.com' to toList in post{} below.
        SENDER_EMAIL   = 'ateebakmal009@gmail.com'   // declared on the Google Form
    }

    stages {

        stage('Checkout latest data') {
            steps {
                checkout scm
                script {
                    // Resolved from the workspace rather than trusting GIT_COMMIT,
                    // so this works however the job is configured.
                    env.COMMIT_SHA = sh(
                        script: 'git rev-parse HEAD',
                        returnStdout: true
                    ).trim()
                    env.COMMITTER_EMAIL = sh(
                        script: 'git log -1 --format=%ae',
                        returnStdout: true
                    ).trim()
                    echo "Building commit ${env.COMMIT_SHA} by ${env.COMMITTER_EMAIL}"
                }
                sh 'git log -1 --pretty="commit %h by %an: %s"'
                sh 'echo "rows in dataset: $(($(wc -l < dataset/train.csv) - 1))"'
            }
        }

        stage('Build image (retrains model)') {
            steps {
                sh '''
                    set -eu
                    docker build \
                      --build-arg GIT_COMMIT="${COMMIT_SHA}" \
                      -t "${IMAGE}:${BUILD_NUMBER}" \
                      -t "${IMAGE}:latest" .
                '''
            }
        }

        stage('Test') {
            steps {
                sh 'docker run --rm "${IMAGE}:${BUILD_NUMBER}" python -m pytest -q'
            }
        }

        // Deploy BEFORE pushing to Docker Hub: the grader's 5-minute window is
        // about the live EC2 service, and a slow registry push must not eat it.
        stage('Deploy on EC2') {
            steps {
                sh '''
                    set -eu
                    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
                    docker run -d \
                      --name "${CONTAINER}" \
                      --restart unless-stopped \
                      -p ${HOST_PORT}:8000 \
                      "${IMAGE}:${BUILD_NUMBER}"
                    docker ps --filter "name=${CONTAINER}" --format "{{.Names}} {{.Status}} {{.Ports}}"
                '''
            }
        }

        stage('Verify redeployment') {
            steps {
                script {
                    // Wait for uvicorn, then assert the LIVE service is serving this
                    // exact commit - catches the case where the old container is
                    // still up because the new one failed to start.
                    env.METRICS_JSON = sh(returnStdout: true, script: '''
                        set -eu
                        for attempt in $(seq 1 40); do
                          if docker exec "${CONTAINER}" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" 2>/dev/null; then
                            break
                          fi
                          sleep 2
                        done

                        docker exec "${CONTAINER}" python -c "
import json, urllib.request
m = json.loads(urllib.request.urlopen('http://127.0.0.1:8000/metrics', timeout=5).read())
assert m['student_id'] == '${STUDENT_ID}', 'wrong student_id: ' + str(m['student_id'])
assert m['git_sha'] == '${COMMIT_SHA}', 'stale deploy, serving ' + str(m['git_sha'])
assert m['training_rows'] >= 100, 'too few training rows'
print(json.dumps(m))
"
                    ''').trim()
                    echo "Live /metrics -> ${env.METRICS_JSON}"
                }
            }
        }

        stage('Push to Docker Hub') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: env.DOCKERHUB_CRED,
                    usernameVariable: 'DH_USER',
                    passwordVariable: 'DH_PASS'
                )]) {
                    sh '''
                        set -eu
                        set +x
                        trap 'docker logout >/dev/null 2>&1 || true' EXIT
                        echo "${DH_PASS}" | docker login -u "${DH_USER}" --password-stdin
                        docker push "${IMAGE}:${BUILD_NUMBER}"
                        docker push "${IMAGE}:latest"
                    '''
                }
            }
        }

        stage('Cleanup old images') {
            steps {
                sh 'docker image prune -f >/dev/null 2>&1 || true'
            }
        }
    }

    post {
        always {
            // No sh step here: post{} can run without a node context, and a
            // throw before emailext would swallow the failure notification.
            script {
                def result = currentBuild.currentResult ?: 'UNKNOWN'

                // Notify the author of the commit that triggered this build, and
                // nobody else. GitHub noreply addresses are dropped because mail
                // to them is discarded rather than delivered.
                def toList = []
                def committer = (env.COMMITTER_EMAIL ?: '').trim()
                if (committer.contains('@') && !committer.contains('noreply')) {
                    toList.add(committer)
                }
                def recipients = toList.join(',')
                echo "Notifying: ${recipients ?: '(nobody - committer address not deliverable)'}"

                if (recipients) {
                    emailext(
                        to: recipients,
                        from: env.SENDER_EMAIL,
                        replyTo: env.SENDER_EMAIL,
                        subject: "${env.STUDENT_ID} - DevOps Lab Midterm - Build #${env.BUILD_NUMBER} - ${result}",
                        mimeType: 'text/plain',
                        body: """CSC418 DevOps for Cloud Computing - Lab Midterm

Student Reg No : ${env.STUDENT_ID}
Sender         : ${env.SENDER_EMAIL}

Build status   : ${result}
Job            : ${env.JOB_NAME} #${env.BUILD_NUMBER}
Git commit     : ${env.COMMIT_SHA ?: 'Unavailable'}
Docker image   : ${env.IMAGE}:${env.BUILD_NUMBER}
Duration       : ${currentBuild.durationString.replace(' and counting', '')}

--- Retrained model, read live from the EC2 container ---
${env.METRICS_JSON ?: '/metrics was not reachable - see the build log'}

Jenkins build  : ${env.BUILD_URL}
"""
                    )
                } else {
                    echo 'WARNING: no valid recipient resolved. Email skipped.'
                }
            }
        }
        success { echo "Deployment of ${env.STUDENT_ID} succeeded." }
        failure { echo "Pipeline failed - see ${env.BUILD_URL}console" }
    }
}
