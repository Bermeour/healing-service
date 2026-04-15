def REPO_NAME = scm.getUserRemoteConfigs()[0].getUrl().tokenize('/').last().split("\\.git")[0]

switch(env.BRANCH_NAME) {

    case "dev":
        configurationName = "serv 184"
        envDeploy = "dev"
        environmentName = "dev"
        portOut = "32774"
        break

    case "release":
        configurationName = "serv 175"
        envDeploy = "uat"
        environmentName = "release"
        portOut = "32775"
        break

    case "master":
        configurationName = "serv 192"
        envDeploy = "prd"
        environmentName = "master"
        portOut = "32776"
        break
}

pipeline {
    triggers {
        pollSCM '* * * * *'
    }

    agent { label 'principal' }

    options {
        disableConcurrentBuilds()
        buildDiscarder(
            logRotator(
                artifactDaysToKeepStr: '30',
                artifactNumToKeepStr: '10',
                daysToKeepStr: '60',
                numToKeepStr: '300'
            )
        )
    }

    environment {
        dir         = "/dod/repository/python"
        dir_modules = "/dod/docker_containers_old/python"
        // Volumen para persistir la base de conocimiento y baselines entre deploys
        data_volume = "/dod/healing-data/$envDeploy"
    }

    stages {

        stage("SCM: Pull code on Remote") {
            when {
                anyOf {
                    branch "dev"
                    branch "release"
                    branch "master"
                }
            }
            steps {
                sshPublisher(
                    continueOnError: false, failOnError: true,
                    publishers: [
                        sshPublisherDesc(
                            configName: "$configurationName",
                            verbose: true,
                            transfers: [
                                sshTransfer(execCommand: """
                                    set -e
                                    cd $dir/$REPO_NAME
                                    git fetch --all
                                    git checkout $environmentName
                                    git pull origin $environmentName
                                """)
                            ]
                        )
                    ]
                )
            }
        }

        stage("Prepare Dirs") {
            when {
                anyOf {
                    branch "dev"
                    branch "release"
                    branch "master"
                }
            }
            steps {
                sshPublisher(
                    continueOnError: false, failOnError: true,
                    publishers: [
                        sshPublisherDesc(
                            configName: "$configurationName",
                            verbose: true,
                            transfers: [
                                sshTransfer(execCommand: """
                                    set -e
                                    mkdir -p $data_volume/baselines
                                    mkdir -p $data_volume/logs
                                    echo "Directorios de datos listos en $data_volume"
                                """)
                            ]
                        )
                    ]
                )
            }
        }

        stage("Delete Old containers") {
            when {
                anyOf {
                    branch "dev"
                    branch "release"
                    branch "master"
                }
            }
            steps {
                sshPublisher(
                    continueOnError: true, failOnError: true,
                    publishers: [
                        sshPublisherDesc(
                            configName: "$configurationName",
                            verbose: true,
                            transfers: [
                                sshTransfer(execCommand: """
                                    set +e
                                    docker rm -f $envDeploy-$REPO_NAME || true
                                    docker rmi -f $envDeploy-$REPO_NAME || true
                                    true
                                """)
                            ]
                        )
                    ]
                )
            }
        }

        stage("Build") {
            when {
                anyOf {
                    branch "dev"
                    branch "release"
                    branch "master"
                }
            }
            steps {
                sshPublisher(
                    continueOnError: false, failOnError: true,
                    publishers: [
                        sshPublisherDesc(
                            configName: "$configurationName",
                            verbose: true,
                            transfers: [
                                sshTransfer(execCommand: """
                                    set -e
                                    cd $dir/$REPO_NAME
                                    docker build --rm -f docker/Dockerfile -t $envDeploy-$REPO_NAME .
                                """)
                            ]
                        )
                    ]
                )
            }
        }

        stage("Deploy: Create a container") {
            when {
                anyOf {
                    branch "dev"
                    branch "release"
                    branch "master"
                }
            }
            steps {
                withCredentials([string(credentialsId: 'secret_id_automation', variable: 'SECRET_ID')]) {
                    sshPublisher(
                        continueOnError: false, failOnError: true,
                        publishers: [
                            sshPublisherDesc(
                                configName: "$configurationName",
                                verbose: true,
                                transfers: [
                                    sshTransfer(execCommand: """
                                        set -e
                                        cd $dir/$REPO_NAME

                                        docker run --restart always -d \\
                                            -e SECRET_ID=\${SECRET_ID} \\
                                            --name $envDeploy-$REPO_NAME \\
                                            --env-file=./docker/env_files/${envDeploy}.env \\
                                            -p $portOut:8765 \\
                                            -v $data_volume:/var/lib/healing \\
                                            $envDeploy-$REPO_NAME
                                    """)
                                ]
                            )
                        ]
                    )
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}
