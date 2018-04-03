#! /usr/bin/env python
# -*- coding: utf-8 -*-

from django.shortcuts import render, HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from .models import Delivery
from .forms import DeliveryFrom
from accounts.permission import permission_verify
from .tasks import new_deploy
import os
from time import sleep
import json
import time
from .file_lib import shell_w_to_file


@login_required()
@permission_verify()
def delivery_list(request):
    temp_name = "delivery/delivery-header.html"
    all_project = Delivery.objects.all()
    results = {
        'temp_name': temp_name,
        'all_project':  all_project,
    }
    return render(request, 'delivery/delivery_list.html', results)


@login_required
@permission_verify()
def delivery_del(request):
    project_id = request.GET.get('project_id', '')
    if project_id:
        Delivery.objects.filter(id=project_id).delete()

    project_id_all = str(request.POST.get('project_id_all', ''))
    if project_id_all:
        for project_id in project_id_all.split(','):
            Delivery.objects.filter(id=project_id).delete()

    return HttpResponseRedirect(reverse('delivery_list'))


@login_required
@permission_verify()
def delivery_add(request):
    temp_name = "delivery/delivery-header.html"
    if request.method == 'POST':
        form = DeliveryFrom(request.POST)
        if form.is_valid():
            form.save()
            p1 = Delivery.objects.get(job_name_id=form.data["job_name"])
            shell_path = "/var/opt/adminset/workspace/{0}/scripts".format(p1.job_name.name)
            if not os.path.isdir(shell_path):
                os.makedirs(shell_path)
            src_path = shell_w_to_file(shell_cmd=form.data["shell"],
                            shell_path=shell_path,
                            shell_name=p1.job_name.name,
                            code_path=p1.job_name.appPath
                            )
            p1.shell_file = src_path
            p1.save()
            return HttpResponseRedirect(reverse('delivery_list'))
    else:
        form = DeliveryFrom()

    results = {
        'form': form,
        'request': request,
        'temp_name': temp_name,
    }
    #print(results["form"])
    return render(request, 'delivery/delivery_base.html', results)


@login_required
@permission_verify()
def delivery_edit(request, project_id):
    project = Delivery.objects.get(id=project_id)
    temp_name = "delivery/delivery-header.html"
    if request.method == 'POST':
        form = DeliveryFrom(request.POST, instance=project)
        print form.data["shell"]
        if form.is_valid():
            form.save()
            p1 = Delivery.objects.get(job_name_id=form.data["job_name"])
            shell_path = "/var/opt/adminset/workspace/{0}/scripts".format(p1.job_name.name)
            if not os.path.isdir(shell_path):
                os.makedirs(shell_path)
            src_path = shell_w_to_file(shell_cmd=form.data["shell"],
                            shell_path=shell_path,
                            shell_name=p1.job_name.name,
                            code_path=p1.job_name.appPath
                            )
            p1.shell_file=src_path
            p1.save()
            return HttpResponseRedirect(reverse('delivery_list'))
    else:
        form = DeliveryFrom(instance=project)

    results = {
        'form': form,
        'project_id': project_id,
        'request': request,
        'temp_name': temp_name,
    }
    return render(request, 'delivery/delivery_base.html', results)


@login_required
@permission_verify()
def delivery_deploy(request, project_id):
    server_list = []
    project = Delivery.objects.get(job_name_id=project_id)
    project.bar_data = 10
    job_name = project.job_name.name
    source_address = project.job_name.source_address
    app_path = project.job_name.appPath
    if project.auth:
        auth_info = {"username": project.auth.username, "password": project.auth.password}
    else:
        auth_info = None
    project.status = True
    project.deploy_num += 1
    project.save()
    sleep(2)
    os.system("mkdir -p /var/opt/adminset/workspace/{0}/logs".format(job_name))
    os.system("mkdir -p /var/opt/adminset/workspace/{0}/scripts".format(job_name))
    if app_path == "/":
        return HttpResponse("app deploy destination cannot /")
        #print(error)
    # foreign key query need add .all()

    servers = project.job_name.serverList.all()
    for server in servers:
        server_ip = str(server.ip)
        server_list.append(server_ip)
    project.bar_data = 15
    deploy_out = new_deploy(job_name, server_list, app_path, source_address, project_id, auth_info)
    print deploy_out
    if deploy_out[0] != "1":
        return HttpResponse("ok")
    else:
        return HttpResponse(deploy_out[1])


@login_required()
@permission_verify()
def log(request, project_id):
    project = Delivery.objects.get(job_name_id=project_id)
    return render(request, "delivery/results.html", locals())


@login_required()
@permission_verify()
def status(request, project_id):
    project = Delivery.objects.get(job_name_id=project_id)
    bar_data = project.bar_data
    status_val = project.status
    ret = {"bar_data": bar_data, "status": status_val}
    data = json.dumps(ret)
    return HttpResponse(data)


@login_required()
@permission_verify()
def log2(request, project_id):
    ret = []
    project = Delivery.objects.get(job_name_id=project_id)
    job_name = project.job_name.name
    try:
        job_workspace = "/var/opt/adminset/workspace/{0}/".format(job_name)
        log_file = job_workspace + 'logs/deploy-' + str(project.deploy_num) + ".log"
        with open(log_file, 'r+') as f:
            line = f.readlines()
        for l in line:
            a = l + "<br>"
            ret.append(a)
    except IOError:
        ret = "Program is Deploying Please waiting<br>"
    return HttpResponse(ret)


@login_required()
@permission_verify()
def task_stop(request, project_id):
    project = Delivery.objects.get(job_name_id=project_id)
    project.bar_data = 0
    project.status = False
    project.save()
    return HttpResponse("task stop ok")

@login_required()
@permission_verify()
def delivery_hueigun(request,project_id):
    temp_name = "delivery/delivery-header.html"
    all_project = Delivery.objects.all()
    results = {
        'temp_name': temp_name,
        'all_project': all_project,
    }
    return render(request, 'delivery/delivery_list.html', results)
