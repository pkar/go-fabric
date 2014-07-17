try:
  from fabric.api import env, run, sudo, put, local, settings, parallel
  from fabric.colors import green, red, yellow
except ImportError:
  print "Install fabric first: sudo easy_install fabric"
  print "Run with: fab command"
  exit(0)

env.forward_agent = True
env.use_ssh_config = True
env.app = 'appname'
env.tests = [env.app,]
env.stage = 'staging'
env.branch = 'staging'
env.path = '/var/apps/%(app)s' % env
env.git_repo = 'git@github.com:pkar/%(app)s.git' % env
env.user = 'user'
env.main = 'src/cmd/main.go'

def production():
  """
  env.hosts = ['host.com', ...]
  """
  env.stage = 'production'
  env.hosts = [
    'host.com', 
  ]
  env.branch = 'production'

def staging():
  """
  env.hosts = ['staging.host.com', ...]
  """
  env.stage = 'production'
  env.hosts = [
    'staging.host.com', 
  ]
  env.branch = 'staging'

def ping():
  """
  ping host servers
  """
  resp = urllib2.urlopen("http://" + env.host + ":9999/ping").read()
  print resp
 
def deploy():
  """
  Try building cross compile and after with docker if available. Restart services.
  """
  build()
  upstart()
  mkdirs()

  put('bin/BUILD', '/tmp/BUILD')
  sudo('mv /tmp/BUILD /var/apps/%(app)s/BUILD' % env)

  put('bin/%(app)s' % env, '/tmp/%(app)s' % env)
  sudo('mv /tmp/%(app)s /var/apps/%(app)s/' % env)

  permissions()
  restart()

def stop():
  """
  Stop all services
  """
  with settings(warn_only=True):
    sudo('initctl stop %(app)s' % env)

def start():
  """
  Start all services
  """
  with settings(warn_only=True):
    sudo('initctl start %(app)s' % env)

def status():
  """
  Status for all services
  """
  sudo('initctl status %(app)s' % env)

def permissions():
  """
  Update application directory permissions.
  """
  sudo('chown -R %(user)s:%(user)s /var/apps/%(app)s' % env)
  sudo('chmod -R g+w /var/apps/%(app)s' % env)

  with settings(warn_only=True):
    sudo('chmod +x /var/apps/%(app)s/%(app)s' % env)

def mkdirs():
  """
  Create required directories and make them group writable.
  """
  sudo('mkdir -p /var/apps/%(app)s' % env)
  sudo('mkdir -p /var/apps/%(app)s/logs' % env)
  permissions()

def upstart():
  """
  Copy %(app)s.conf /etc/init/
  """
  mkdirs()
  upstart = """description     "%(app)s"

start on filesystem
stop on runlevel [!2345]

respawn limit 10 5

exec su - deploy -c '/var/apps/%(app)s/%(app)s -env=%(stage)s -log_dir=%(path)s/logs -v=1 -port=9999'
  """ % env

  put(StringIO.StringIO(upstart), '/tmp/%(app)s.conf' % env)
  sudo('mv /tmp/%(app)s.conf /etc/init/' % env)

def uninstall():
  """
  Remove all installed files
  """
  sudo('rm -rf /var/apps/%(app)s' % env)
  sudo('rm -f /etc/init/%(app)s.conf' % env)

def build():
  """
  Build binaries
  """
  local('echo "%(user)s" > bin/BUILD' % env)
  local('echo `date` >> bin/BUILD')
  local('echo `git log --pretty=oneline -1` >> bin/BUILD')
  local('echo $(go version) >> bin/BUILD')

  local('GOPATH=`pwd` GOARCH=amd64 GOOS=linux go build -o bin/%(app)s %(main)s' % env)

def pretty_result(result, name):
  if result.failed:
    print red("FAILED: " + name)
    print red('-'*80)
  else:
    print green("OK: " + name)
    print green('-'*80)
  print

def test_coverage(name=None):
  """
  Get coverage analysis, `fab coverage:models`.
  """
  local("mkdir -p bin/testdata")

  if name:
    result = local('go test -cover -coverprofile=bin/testdata/' + name.replace("/", ".") + '.out ' + name)
    pretty_result(result, name)
  else:
    for name in env.tests:
      result = local('go test -cover -coverprofile=bin/testdata/' + name.replace("/", ".") + '.out ' + name)
      pretty_result(result, name)

def test_bench(name=None):
  """
  Run tests along with any benchmark tests defined.
  """
  if name:
    result = local('GOPATH=`pwd` go test ' + name + ' -bench=.*')
    pretty_result(result, name)
  else:
    for t in env.tests:
      result = local('GOPATH=`pwd` go test ' + t + ' -bench=.*')
      pretty_result(result, t)

def test(x=None, verbose=True, vet=False):
  """
  Run unit and integration tests.
  """
  with settings(warn_only=True):
    if x:
      result = None
      if vet:
        result = local('GOPATH=`pwd` go vet ' + x)
      else:
        if verbose:
          result = local('GOPATH=`pwd` go test -v ' + x + ' -logtostderr')
        else:
          result = local('GOPATH=`pwd` go test ' + x)
      pretty_result(result, x)
    else:
      for t in env.tests:
        result = None
        if vet:
          result = local('GOPATH=`pwd` go vet ' + t)
        else:
          if verbose:
            result = local('GOPATH=`pwd` go test -v ' + t + ' -logtostderr')
          else:
            result = local('GOPATH=`pwd` go test ' + t)
        pretty_result(result, t)
