import http from 'http';
import httpProxy from 'http-proxy';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

// Start Python server on port 9898 if not already running
const pythonProcess = spawn('python3', ['server/main.py'], {
  stdio: 'inherit',
  cwd: process.cwd()
});

pythonProcess.on('error', (err) => {
  console.error('Failed to start Python backend:', err);
});

const proxy = httpProxy.createProxyServer({
  target: 'http://127.0.0.1:9898',
  ws: true
});

proxy.on('error', (err, req, res) => {
  if (res && res.writeHead) {
    res.writeHead(502, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end('<h3>PS5 PKG Sender is starting up, please wait a few seconds and refresh...</h3>');
  }
});

const server = http.createServer((req, res) => {
  proxy.web(req, res);
});

server.on('upgrade', (req, socket, head) => {
  proxy.ws(req, socket, head);
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, '0.0.0.0', () => {
  console.log(`AI Studio Dev Gateway listening on port ${PORT} -> proxying to Python backend :9898`);
});

process.on('SIGTERM', () => {
  pythonProcess.kill('SIGTERM');
  process.exit(0);
});
process.on('SIGINT', () => {
  pythonProcess.kill('SIGINT');
  process.exit(0);
});
