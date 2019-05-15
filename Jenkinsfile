pipeline {
  agent any

  options {
    copyArtifactPermission(projectNames: 'blazar*')
  }

  stages {
    stage('test') {
      parallel {
        stage('pep8') {
          steps {
            sh 'source scl_source enable rh-python35 && tox -e pep8'
          }
        }
        stage('py27') {
          steps {
            sh 'tox -e py27'
          }
        }
      }
    }

    stage('package') {
      steps {
        dir('dist') {
          deleteDir()
        }
        sh 'python setup.py sdist'
        sh 'find dist -type f -exec cp {} dist/blazar.tar.gz \\;'
        archiveArtifacts(artifacts: 'dist/blazar.tar.gz', onlyIfSuccessful: true)
      }
    }
  }
}
