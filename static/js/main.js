var term,
    protocol,
    socketURL,
    socket;

var terminalContainer = document.getElementById('terminal-container');
var optionElements = {
    cursorBlink: document.querySelector('#option-cursor-blink')
};

optionElements.cursorBlink.addEventListener('change', createTerminal);

createTerminal();

function GetQueryString(name) {
    var reg = new RegExp("(^|&)" + name + "=([^&]*)(&|$)");
    var r = window.location.search.substr(1).match(reg);
    if (r != null) {
        return unescape(r[2]);
    }
    else {
        return null;
    }

}
function createTerminal() {
    while (terminalContainer.children.length) {
        terminalContainer.removeChild(terminalContainer.children[0]);
    }
    term = new Terminal({
        cursorBlink: optionElements.cursorBlink.checked
    });
    var namespace = '/sshclient';
    var room_name = GetQueryString('roomname');
    var socket = io.connect('http://' + document.domain + ':' + location.port + namespace);
    socket.room_name = room_name;
    socket.emit('join', {room: room_name}); //加入房间
    term.open(terminalContainer);
    term.fit();

    socket.on('connect', function () {
        runRealTerminal(socket);
    });
    socket.on('close', function () {
        runFakeTerminal();
    });
    socket.on('error', function () {
        runFakeTerminal();
    });
}


function runRealTerminal(socket) {
    term.attach(socket);
    term._initialized = true;
}

function runFakeTerminal() {
    if (term._initialized) {
        return;
    }
    term._initialized = true;

    var shellprompt = '$ ';

    term.prompt = function () {
        term.write('\r\n' + shellprompt);
    };

    term.writeln('Welcome to xterm.js');
    term.writeln('This is a local terminal emulation, without a real terminal in the back-end.');
    term.writeln('Type some keys and commands to play around.');
    term.writeln('');
    term.prompt();

    term.on('key', function (key, ev) {
        var printable = (
            !ev.altKey && !ev.altGraphKey && !ev.ctrlKey && !ev.metaKey
        );

        if (ev.keyCode == 13) {
            term.prompt();
        } else if (ev.keyCode == 8) {
            /*
             * Do not delete the prompt
             */
            if (term.x > 2) {
                term.write('\b \b');
            }
        } else if (printable) {
            term.write(key);
        }
    });
}
