import json
import glob
import os

import click
import docker
import yaml


TEMPLATE = """
FROM jupyter/minimal-notebook:7a0c7325e470

USER root
COPY {SRC} /tmp/environment.yaml

RUN conda env create -f /tmp/environment.yaml

RUN bash -c "source activate {KERNEL_NAME}" \
    && conda install ipykernel --freeze-installed \
    && python -m ipykernel install --name {KERNEL_NAME} --display {KERNEL_NAME}

RUN conda clean -afy \
    && find /opt/conda/ -follow -type f -name '*.a' -delete \
    && find /opt/conda/ -follow -type f -name '*.pyc' -delete \
    && find /opt/conda/ -follow -type f -name '*.js.map' -delete \

RUN fix-permissions $CONDA_DIR
"""


def load_env_definition(path):
    with open(path) as f:
        return yaml.load(f)


def generate_template(outpath, **kwargs):
    raw = TEMPLATE.format(**kwargs)

    with open(outpath, 'w') as f:
        f.write(raw)

    return raw


@click.group()
def cli():
    pass


def echo(msg, nl=False,  **kwargs):
    click.echo(msg, err=True, nl=nl, **kwargs)


def _build(config, template, tag, dockerfile):
    conda_env = load_env_definition(config)
    env_name = conda_env['name']

    if not os.path.exists('dockerfiles'):
        os.makedirs('dockerfiles')

    if not dockerfile:
        dockerfile = 'dockerfiles/Dockerfile-{}'.format(env_name)
        generate_template(dockerfile, SRC=config, KERNEL_NAME=env_name)

    image_tag = '{}:{}'.format(env_name, tag)

    docker_args = dict(
        tag=image_tag,
        path='.',
        dockerfile=dockerfile
    )

    click.echo("building Dockerfile {} ....".format(dockerfile))

    if template:
        click.echo("Generated {}".format(dockerfile))
        return

    dockerclient = docker.APIClient(base_url='unix://var/run/docker.sock')

    logs = dockerclient.build(**docker_args)

    for log in logs:
        log = json.loads(log)
        if 'stream' in log:
            echo(log['stream'])
        elif 'error' in log:
            echo(log['error'])
        else:
            echo(json.dumps(log), nl=True)


@cli.command()
@click.option(
    '--config', default='environment.yaml',
    help='conda environment file')
@click.option(
    '--template', is_flag=True,
    help='generate docker files only, no building')
@click.option('--tag', default='latest', help='image tag')
@click.option(
    '--dockerfile', default=None,
    help='pass your own dockerfile instead')
def build(config, template, tag, dockerfile):
    _build(config, template, tag, dockerfile)


@cli.command()
@click.option(
    '--dirname', default='environments/',
    help='directory of yaml files')
@click.option('--tag', default='latest', help='image tag')
@click.option(
    '--template', is_flag=True,
    help='generate docker files only, no building')
def generate_images(dirname, tag, template):
    base = os.path.join(dirname, '*.yaml')
    for envfile in glob.glob(base):
        _build(envfile, template=template, tag=tag, dockerfile=None)
        click.echo('Done...\n')


if __name__ == '__main__':
    cli()
