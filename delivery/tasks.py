#! /usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from celery import shared_task
from .models import Delivery
#import os
import shutil

import sh, time
#from .nginx import *
from .haproxy import *
from .code_release_mode import code_release
from .ansible_api import Ansible_cmd
from .code_release_mode import code_rsync_dest
from .file_lib import git_log_file


@shared_task
def new_deploy(job_name, server_list, app_path, source_address, project_id, auth_info):
    opt = locals()
    server_list_len = 0
    code_tongbu = []

    def baocuen(bar_data,status):
        p1.bar_data = bar_data
        p1.status = status
        p1.save()

    for key in opt:
        if opt[key] == None and key != "auth_info":
            return "%s is None" % key
    cmd = ""
    p1 = Delivery.objects.get(job_name_id=project_id)
    java_pack_path = res_build()
    job_workspace = "/var/opt/adminset/workspace/{0}/".format(job_name)
    pack_workspace = "/var/opt/adminset/workspace/{0}/build_pack/{1}".format(job_name,java_pack_path)
    log_path = job_workspace + 'logs/'
    log_name = 'deploy-' + str(p1.deploy_num) + ".log"

    with open(log_path + log_name, 'wb+') as f:
        f.writelines("<h4>Deploying project {0} for {1}th</h4>".format(job_name, p1.deploy_num))
    if not app_path.endswith("/"):
        app_path += "/"

    if isinstance(server_list, list) and len(server_list) > 1:
        server_list_1 = server_list[:int(len(server_list) / 2)]
        server_list_2 = server_list[(len(server_list) / 2):]
        server_list_len = 2
    else:
        server_list_len = 1
        server_list_1 = server_list

    with open(log_path + log_name, 'ab+') as f:
        f.writelines(u"<br>本次发布代码更新主机包括：<br> {0} <br>负载均衡地址: <br>{1}<h5></h5>".format(
            "<br>".join(server_list),
            p1.job_name.lvs_host_ip
        )
    )
    host_test_list = server_list
    host_test_list.append(p1.job_name.lvs_host_ip)
    host_test_list_2 = list(set(host_test_list))
    host_net_t = Ansible_cmd(host_test_list_2)
    test_out = host_net_t.ping().split("\n")
    test_error_host = []
    print host_test_list_2
    for I in host_test_list_2:
        for U in test_out:
            if I in U:
                if "SUCCESS" not in U:
                    test_error_host.append(I)
                    break

    if p1.job_name.source_type == "git":
        cmd = git_clone(job_workspace,
                        auth_info,
                        source_address,
                        p1)
    if p1.job_name.source_type == "svn":
        cmd = svn_clone(job_workspace,
                        auth_info,
                        source_address,
                        p1)
    data = cmd_exec(cmd)
    p1.bar_data = 10
    p1.save()
    with open(log_path + log_name, 'ab+') as f:
        f.writelines("{0}<br>{1}".format(cmd,data))

    with open(log_path + log_name, 'ab+') as f:
        f.writelines(u"JAVA打包--开始<br>")
    ansible_api = Ansible_cmd("127.0.0.1")

    java_pack_name = "{0}.war".format(p1.job_name.name)
    print "{0}code/{1}".format(job_workspace,p1.job_name.name),pack_workspace,java_pack_name
    pak_out = ansible_api.java_pack("{0}code/{1}".format(job_workspace,p1.job_name.name),pack_workspace,java_pack_name)
    with open(log_path + log_name, 'ab+') as f:
        f.writelines(u"{0}<br>".format(pak_out))
        f.writelines(u"JAVA打包--完成<br>")



    if p1.job_name.config_file != None and p1.conf_file_update_time != None:
        conf_update_time = cmd_exec(git_log_file(p1.job_name.config_file))
        update_time = p1.conf_file_update_time
        if str(conf_update_time) != str(update_time):
            baocuen(15, False)
            return ["1","配置文件有更新！"]

    if len(test_error_host) > 0:
        with open(log_path + log_name, 'ab+') as f:
            f.writelines(u"<br>测试目标主机网络异常<br> {0} <br>停止代码发布<h5></h5>".format("<br>".join(test_error_host)))
        baocuen(20, False)
        return ["2"]

    #分批发布代码
    if server_list_len == 2:
        # 第一组主机
        lvs_zhuji = code_release(host_group=server_list_1,
                                 lvs_group=p1.job_name.lvs_host_ip,
                                 config_path=p1.job_name.configPath,
                                 dest_path=p1.job_name.lvs_cofnig_path,
                                 lvs_name=p1.job_name.lvs_type,
                                 logfile=log_path + log_name,
                                 code_src=pack_workspace,
                                 code_dest="/war/{0}".format(p1.job_name.appPath),
                                 java_script=p1.job_name.java_script,
                                 work_path=p1.job_name.appPath,
                                 obj_name=[p1.job_name.name,java_pack_path],
                                 shell_file=p1.shell_file,
                                 exclude=p1.job_name.raync_exclude)
        if lvs_zhuji:
            baocuen(80,True)
        else:
            baocuen(40, False)
            return ["2"]
        with open(log_path + log_name, 'ab+') as f:
            f.writelines("<br><h5>Deploying project {0} for {1}th</h5>".format(job_name, p1.deploy_num))
        #第二组主机
        lvs_zhuji = code_release(host_group=server_list_2,
                                 lvs_group=p1.job_name.lvs_host_ip,
                                 config_path=p1.job_name.configPath,
                                 dest_path=p1.job_name.lvs_cofnig_path,
                                 lvs_name=p1.job_name.lvs_type,
                                 logfile=log_path + log_name,
                                 #code_src="{0}/{1}.war".format(job_workspace),
                                 code_src="{0}/{1}".format(pack_workspace, java_pack_name),
                                 code_dest="/war/{0}".format(p1.job_name.appPath),
                                 java_script=p1.job_name.java_script,
                                 work_path=p1.job_name.appPath,
                                 obj_name=[p1.job_name.name,java_pack_path],
                                 shell_file=p1.shell_file,
                                 exclude=p1.job_name.raync_exclude)
        if lvs_zhuji:
            baocuen(130, True)
        else:
            baocuen(130, False)
            return ["2"]

    elif server_list_len == 1:
        code_rsync_dest(host_group=server_list_1,
                        #code_src="{0}/code/".format(job_workspace),
                        code_src="{0}/{1}".format(pack_workspace, java_pack_name),
                        code_dest="/war/{0}".format(p1.job_name.appPath),
                        java_script=p1.job_name.java_script,
                        work_path=p1.job_name.appPath,
                        obj_name=p1.job_name.name,
                        logfile=log_path + log_name,
                        shell_file=p1.shell_file,
                        exclude=p1.job_name.raync_exclude)
    else:
        baocuen(130, False)
        with open(log_path + log_name, 'ab+') as f:
            f.writelines(u"<h4>没有主机IP地址！</h4>")
    baocuen(130, False)
    with open(log_path + log_name, 'ab+') as f:
        f.writelines("<h4>Project {0} have deployed for {1}th</h4>".format(p1.job_name, p1.deploy_num))
    return code_tongbu

def parser_url(source_address, url_len, user_len, auth_info, url_type=None):
    if url_type:
        new_suffix = source_address[url_len:][user_len:]
        final_add = source_address[:url_len] + auth_info["username"] + ":" + auth_info["password"] + new_suffix
    else:
        new_suffix = source_address[url_len:]
        final_add = source_address[:url_len] + auth_info["username"] + ":" + auth_info["password"] + new_suffix
    return final_add

def git_clone(job_workspace, auth_info, source_address, p1):
    if os.path.exists("{0}code/{1}/.git".format(job_workspace,p1.job_name.name)):
        cmd = "cd {0}code/{1} && git pull".format(job_workspace,p1.job_name.name)
        return cmd
    if not os.path.exists("{0}/code/{1}".format(job_workspace,p1.job_name.name)):
        os.makedirs("{0}/code/{1}".format(job_workspace,p1.job_name.name))
        print "{0}/code/{1}".format(job_workspace,p1.job_name.name)
    if p1.version:
        cmd = "git clone {0} {1}code/{3}/".format(source_address, job_workspace, p1.version,p1.job_name.name)
    else:
        cmd = "git clone {0} {1}code/{2}".format(source_address, job_workspace,p1.job_name.name)
    return cmd


def svn_clone(job_workspace, auth_info, source_address, p1):
    if p1.version:
        if not source_address.endswith("/") and not p1.version.endswith('/'):
            source_address += '/'
        source_address += p1.version
    if os.path.exists("{0}code/.svn".format(job_workspace)):
        cmd = "svn --non-interactive --trust-server-cert --username {2} --password {3} update {0} {1}code/".format(
                source_address, job_workspace, auth_info["username"], auth_info["password"])
    else:
        cmd = "svn --non-interactive --trust-server-cert --username {2} --password {3} checkout {0} {1}code/".format(
                source_address, job_workspace, auth_info["username"], auth_info["password"])
    return cmd


def del_build_code(path):
    """清理原有发布的生成的代码"""
    try:
        shutil.rmtree("{0}code/".format(path))
        return ["{0}code/".format(path),"success",0]
    except StandardError as msg:
        return ["{0}code/".format(path), "path file None or file Non permissions deleting",1]

def res_build():
    """传入后缀"""
    date_time_re = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    return "{0}".format(date_time_re)