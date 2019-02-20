pipeline {
  agent any
 
  options {
    copyArtifactPermission(projectNames: 'blazar*')
  }

  stages {
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

