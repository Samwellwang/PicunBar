const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

const PORT = 4567;
const HTML_PATH = path.join(__dirname, 'picun_controller.html');

const server = http.createServer((req, res) => {
  if (fs.existsSync(HTML_PATH)) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(fs.readFileSync(HTML_PATH));
  } else {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Not Found');
  }
});

server.listen(PORT, '127.0.0.1', () => {
  const url = `http://127.0.0.1:${PORT}`;
  console.log(`\n🎧 Picun F8 Ultra 控制器已启动！`);
  console.log(`👉 访问地址: ${url}`);
  console.log(`按 Ctrl+C 可停止服务。\n`);

  // 自动打开浏览器
  exec(`open "${url}"`);
});
