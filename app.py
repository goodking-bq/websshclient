#!/usr/bin/env python
# coding:utf-8
from __future__ import unicode_literals, absolute_import, print_function
from flask import Flask, render_template, session, request, jsonify, g
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

# try:
#     import interactive
# except ImportError:
#     from . import interactive
# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None


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


def manual_auth(username, hostname, password=None):
    default_auth = 'p'
    auth = default_auth

    if auth == 'r':
        default_path = os.path.join(os.environ['HOME'], '.ssh', 'id_rsa')
        path = input('RSA key [%s]: ' % default_path)
        if len(path) == 0:
            path = default_path
        try:
            key = paramiko.RSAKey.from_private_key_file(path)
        except paramiko.PasswordRequiredException:
            password = getpass.getpass('RSA key password: ')
            key = paramiko.RSAKey.from_private_key_file(path, password)
        t.auth_publickey(username, key)
    elif auth == 'd':
        default_path = os.path.join(os.environ['HOME'], '.ssh', 'id_dsa')
        path = input('DSS key [%s]: ' % default_path)
        if len(path) == 0:
            path = default_path
        try:
            key = paramiko.DSSKey.from_private_key_file(path)
        except paramiko.PasswordRequiredException:
            password = getpass.getpass('DSS key password: ')
            key = paramiko.DSSKey.from_private_key_file(path, password)
        t.auth_publickey(username, key)
    else:
        t.auth_password(username, password)


def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        socketio.sleep(10)
        count += 1
        socketio.emit('my response',
                      {'data': 'Server generated event', 'count': count},
                      namespace='/test')


@app.route('/')
def index():
    # global thread
    # if thread is None:
    #     thread = socketio.start_background_task(target=background_thread)
    return render_template('index.html', async_mode=socketio.async_mode)


@app.route('/terminal/')
def terminal():
    return render_template('terminal.html')


@app.route('/client_login/', methods=['POST'])
def client_login():
    user = request.form.get('user')
    password = request.form.get('password')
    host = request.form.get('host')
    port = request.form.get('port')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # socketio.emit('new ssh client', {'data': {'host': host, 'port': int(port), 'user': user, 'password': password}},
    #               namespace='/test')
    try:
        ssh.connect(hostname=b'zousj.cn', port=7726, username=b'root', password=b'www.zousj.cn@golsee7726')
        # session['ssh'] = ssh # 不能赋给session
        socketio.ssh = ssh
        return jsonify({'data': 'login success', 'errors': 0})
    except Exception as e:
        print(e)
        return jsonify({'data': '登陆失败', 'errors': 1})


@app.route('/exec/', methods=['POST', 'GET'])
def execs():
    print(g.get('ssh', None))
    return jsonify({"result": "aaaa"})


@socketio.on('my event', namespace='/test')
def test_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': message['data'], 'count': session['receive_count']})


@socketio.on('ssh login', namespace='/test')
def ssh_login(message):
    hostname = message['host']
    port = message['port']
    username = message['user']
    password = message['password']
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((hostname, int(port)))
    except Exception as e:
        emit('ssh login response', {'data': e.message})
    try:
        t = paramiko.Transport(sock)
        try:
            t.start_client()
        except paramiko.SSHException:
            emit('ssh login response', {'data': '*** SSH negotiation failed.'})
        try:
            keys = paramiko.util.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
        except IOError:
            try:
                keys = paramiko.util.load_host_keys(os.path.expanduser('~/ssh/known_hosts'))
            except IOError:
                print('*** Unable to open host keys file')
                emit('ssh login response', {'data': '*** Unable to open host keys file'})

        # check server's host key -- this is important.
        key = t.get_remote_server_key()
        if hostname not in keys:
            print('*** WARNING: Unknown host key!')
            emit('ssh login response', {'data': '*** WARNING: Unknown host key!'})
        elif key.get_name() not in keys[hostname]:
            print('*** WARNING: Unknown host key!')
            emit('ssh login response', {'data': '*** WARNING: Unknown host key!'})
        elif keys[hostname][key.get_name()] != key:
            print('*** WARNING: Host key has changed!!!')
            emit('ssh login response', {'data': '*** WARNING: Host key has changed!!!'})
        else:
            print('*** Host key OK.')
            emit('ssh login response', {'data': '*** Host key OK.'})

        # get username
        if username == '':
            default_username = getpass.getuser()
            if len(username) == 0:
                username = default_username
    except Exception as e:
        emit('ssh login response', {'data': e.message})
        agent_auth(t, username)
        if not t.is_authenticated():
            t.auth_password(username, password)
            # manual_auth(username, hostname)
        if not t.is_authenticated():
            print('*** Authentication failed. :(')
            emit('ssh login response', {'data': '*** Authentication failed. :('})
            t.close()
        else:
            emit('ssh login response', {'data': 'login success'})

            #
            # chan = t.open_session()
            # chan.get_pty()
            # chan.invoke_shell()
            # print('*** Here we go!\n')
            # interactive.interactive_shell(chan)
            # chan.close()
            # t.close()


@socketio.on('exec command', namespace='/test')
def exec_command(message):
    try:
        stdin, stdout, stderr = socketio.ssh.exec_command(message['data'])
        emit('command result',
             {'data': stderr.read() or stdout.read(), 'count': session['receive_count']})
    except Exception as e:
        emit('command result',
             {'data': e.message, 'count': session['receive_count']})


@socketio.on('my broadcast event', namespace='/test')
def test_broadcast_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': message['data'], 'count': session['receive_count']},
         broadcast=True)


@socketio.on('join', namespace='/test')
def join(message):
    join_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': 'In rooms: ' + ', '.join(rooms()),
          'count': session['receive_count']})


@socketio.on('leave', namespace='/test')
def leave(message):
    leave_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': 'In rooms: ' + ', '.join(rooms()),
          'count': session['receive_count']})


@socketio.on('close room', namespace='/test')
def close(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response', {'data': 'Room ' + message['room'] + ' is closing.',
                         'count': session['receive_count']},
         room=message['room'])
    close_room(message['room'])


@socketio.on('my room event', namespace='/test')
def send_room_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': message['data'], 'count': session['receive_count']},
         room=message['room'])


@socketio.on('disconnect request', namespace='/test')
def disconnect_request():
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': 'Disconnected!', 'count': session['receive_count']})
    disconnect()


@socketio.on('my ping', namespace='/test')
def ping_pong():
    emit('my pong')


@socketio.on('connect', namespace='/test')
def test_connect():
    emit('my response', {'data': 'Connected', 'count': 0})


@socketio.on('disconnect', namespace='/test')
def test_disconnect():
    print('Client disconnected', request.sid)


if __name__ == '__main__':
    socketio.run(app, debug=True)
