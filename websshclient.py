#!/usr/bin/env python
# coding:utf-8
from __future__ import absolute_import, unicode_literals, print_function
from flask import Flask, render_template, session, request, jsonify, g, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect
import paramiko
import base64
from binascii import hexlify
import getpass
import os
import select
import socket
import sys
import time
import traceback
from paramiko.py3compat import input

import paramiko

__author__ = 'golden'
__date__ = '2016/7/24'
"""
说明：
----------
xterm.js 结合 falsk +flask-socketio+paramiko实现的web ssh客户端

socketio:
namespace:'/sshclient'

*ssh response* 执行shell后的返回

"""
async_mode = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)


def agent_auth(transport, username):
    """
    Attempt to authenticate to the given transport using any of the private
    keys available from an SSH agent.
    """

    agent = paramiko.Agent()
    agent_keys = agent.get_keys()
    if len(agent_keys) == 0:
        return

    for key in agent_keys:
        print('Trying ssh-agent key %s' % hexlify(key.get_fingerprint()))
        try:
            transport.auth_publickey(username, key)
            print('... success!')
            return
        except paramiko.SSHException:
            print('... nope.')


def windows_shell(sock, room_name):
    while True:
        data = sock.recv(256)
        if not data:
            break
        socketio.emit('ssh response',
                      {'data': data.decode('utf-8', 'replace')}, namespace='/sshclient', room=room_name)


@app.route('/', methods=['POST', 'GET'])
def index():
    """
    提交表单时 创建ssh 连接
    :return:
    """
    if request.method == 'POST':
        form = request.form
        hostname = form.get('hostname')
        port = form.get('port')
        user = form.get('user')
        password = form.get('password', 22)
        room_name = form.get('room_name')
        session[room_name] = {'hostname': hostname,
                              'port': port,
                              'user': user,
                              'password': password}
        return redirect(url_for('.index'))
    return render_template('index.html')


@app.route('/client')
def client():
    return render_template('client.html')


@socketio.on('join', namespace='/sshclient')
def join(message):
    join_room(message['room'])
    hostname = session[message['room']]['hostname']
    username = session[message['room']]['username']
    port = int(session[message['room']]['port'])
    password = session[message['room']]['password']
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((hostname, int(port)))
    except Exception as e:
        emit('onmessage', {'data': e.message})
    try:
        t = paramiko.Transport(sock)
        try:
            t.start_client()
        except paramiko.SSHException:
            emit('onmessage', {'data': '*** SSH negotiation failed.'})
        try:
            keys = paramiko.util.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
        except IOError:
            try:
                keys = paramiko.util.load_host_keys(os.path.expanduser('~/ssh/known_hosts'))
            except IOError:
                print('*** Unable to open host keys file')
                emit('onmessage', {'data': '*** Unable to open host keys file'})

        # check server's host key -- this is important.
        key = t.get_remote_server_key()
        if hostname not in keys:
            print('*** WARNING: Unknown host key!')
            emit('onmessage', {'data': '*** WARNING: Unknown host key!'})
        elif key.get_name() not in keys[hostname]:
            print('*** WARNING: Unknown host key!')
            emit('onmessage', {'data': '*** WARNING: Unknown host key!'})
        elif keys[hostname][key.get_name()] != key:
            print('*** WARNING: Host key has changed!!!')
            emit('onmessage', {'data': '*** WARNING: Host key has changed!!!'})
        else:
            print('*** Host key OK.')
            emit('onmessage', {'data': '*** Host key OK.'})

        # get username
        if username == '':
            default_username = getpass.getuser()
            if len(username) == 0:
                username = default_username
    except Exception as e:
        agent_auth(t, username)
        if not t.is_authenticated():
            t.auth_password(username, password)
            # manual_auth(username, hostname)
        if not t.is_authenticated():
            print('*** Authentication failed. :(')
            emit('onmessage', {'data': '*** Authentication failed. :('})
            t.close()
        else:
            emit('onmessage', {'data': 'login success'})
        chan = t.open_session()
        chan.get_pty()
        chan.invoke_shell()
        if not hasattr(app, 'extensions'):
            app.extensions = {'sshpool': {}}
        if 'sshpool' in app.extensions.keys():
            app.extensions['sshpool'].update({
                message['room']: {'chan': chan,
                                  'chan_thread': socketio.start_background_task(windows_shell, sock=chan,
                                                                                room_name=message['room'])}})
        else:
            app.extensions['sshpool'] = {
                message['room']: {'chan': chan,
                                  'chan_thread': socketio.start_background_task(windows_shell, sock=chan,
                                                                                room_name=message['room'])}}
        print(chan)
        socketio.emit('ssh response', {'data': '%s conncet' % hostname}, namespace='/sshclient',
                      room=message['room'])  # 发送一个连接信息
        emit('ssh response',
             {'data': '进入：' + ', '.join(rooms())}, room=message['room'])


@socketio.on('ssh command', namespace='/sshclient')
def ssh_command(message):
    room = message['room']
    if room:
        try:
            print(message)
            print(app.extensions)
            chan = app.extensions['sshpool'][room]['chan']
            for r in message['data']:
                chan.send(r)
        except Exception as e:
            raise Exception(e)
    else:
        raise Exception(u'没有room')


if __name__ == '__main__':
    socketio.run(app, debug=True)
