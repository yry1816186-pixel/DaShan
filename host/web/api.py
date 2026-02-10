import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio

from .websocket import WebSocketBroadcaster, WebSocketManager, WebSocketMessage

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.broadcaster = WebSocketBroadcaster()
    app.state.ws_manager = WebSocketManager(app.state.broadcaster)
    
    logger.info("DaShan API starting...")
    yield
    
    logger.info("DaShan API shutting down...")


def create_app(
    title: str = "DaShan Dashboard API",
    version: str = "2.0.0",
    host: str = "0.0.0.0",
    port: int = 8000,
    enable_cors: bool = True
) -> FastAPI:
    app = FastAPI(
        title=title,
        version=version,
        lifespan=lifespan
    )
    
    if enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    setup_routes(app)
    
    return app


def setup_routes(app: FastAPI):
    @app.get("/")
    async def root():
        return {
            "name": "DaShan Dashboard API",
            "version": "2.0.0",
            "status": "running",
            "endpoints": {
                "api": "/api",
                "websocket": "/ws",
                "docs": "/docs",
                "dashboard": "/dashboard"
            }
        }
    
    @app.get("/api/health")
    async def health_check():
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }
    
    @app.get("/api/stats")
    async def get_stats():
        return {
            "broadcaster": app.state.broadcaster.get_stats(),
            "websocket": app.state.ws_manager.get_stats(),
            "system": {
                "timestamp": datetime.now().isoformat(),
                "uptime": "unknown"
            }
        }
    
    @app.get("/api/history")
    async def get_history(limit: int = 50):
        return app.state.broadcaster.get_history(limit)
    
    @app.get("/api/clients")
    async def get_clients():
        return app.state.ws_manager.get_all_clients()
    
    @app.post("/api/broadcast")
    async def broadcast_message(message: Dict[str, Any]):
        event_type = message.get("event_type", "custom")
        data = message.get("data", {})
        
        app.state.ws_manager.broadcast_to_subscribers(
            event_type,
            data,
            source="api"
        )
        
        return {
            "success": True,
            "event_type": event_type,
            "timestamp": datetime.now().isoformat()
        }
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        client_id = websocket.query_params.get("client_id", f"client_{datetime.now().timestamp()}")
        
        await websocket.accept()
        
        queue = asyncio.Queue()
        
        await app.state.ws_manager.connect(client_id, queue)
        
        try:
            receive_task = asyncio.create_task(receive_messages(websocket, client_id, queue))
            send_task = asyncio.create_task(send_messages(websocket, queue))
            
            done, pending = await asyncio.wait(
                [receive_task, send_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {client_id}")
        
        finally:
            await app.state.ws_manager.disconnect(client_id, queue)
    
    @app.get("/dashboard")
    async def dashboard():
        html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DaShan Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        header {
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 30px;
        }
        header h1 {
            font-size: 2.5em;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .status-bar {
            display: flex;
            justify-content: space-between;
            padding: 15px 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #00ff88;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,212,255,0.2);
        }
        .card h3 {
            color: #00d4ff;
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        .card .value {
            font-size: 2em;
            font-weight: bold;
            margin: 10px 0;
        }
        .log-container {
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            padding: 20px;
            max-height: 400px;
            overflow-y: auto;
        }
        .log-entry {
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        .log-entry .time {
            color: #888;
            margin-right: 10px;
        }
        .log-entry .event {
            color: #00d4ff;
            margin-right: 10px;
        }
        .log-entry .data {
            color: #ccc;
        }
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        button {
            padding: 12px 24px;
            background: linear-gradient(135deg, #00d4ff, #7b2cbf);
            border: none;
            border-radius: 8px;
            color: white;
            font-size: 1em;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover {
            transform: scale(1.05);
        }
        button:active {
            transform: scale(0.98);
        }
        .connection-status {
            padding: 10px 15px;
            border-radius: 8px;
            font-weight: bold;
        }
        .connected {
            background: rgba(0,255,136,0.2);
            color: #00ff88;
        }
        .disconnected {
            background: rgba(255,100,100,0.2);
            color: #ff6464;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 DaShan Dashboard</h1>
            <p>实时监控系统 V2.0</p>
        </header>

        <div class="status-bar">
            <div class="status-item">
                <div class="status-indicator"></div>
                <span>系统运行中</span>
            </div>
            <div class="status-item">
                <span id="connectionStatus" class="connection-status disconnected">未连接</span>
            </div>
            <div class="status-item">
                <span>运行时间: <span id="uptime">0s</span></span>
            </div>
        </div>

        <div class="controls">
            <button onclick="startListening()">🎤 开始监听</button>
            <button onclick="stopListening()">⏹ 停止监听</button>
            <button onclick="clearLogs()">🗑 清除日志</button>
        </div>

        <div class="grid">
            <div class="card">
                <h3>连接数</h3>
                <div class="value" id="connections">0</div>
                <p>活跃WebSocket连接</p>
            </div>
            <div class="card">
                <h3>消息数</h3>
                <div class="value" id="messages">0</div>
                <p>总消息数</p>
            </div>
            <div class="card">
                <h3>系统状态</h3>
                <div class="value" style="font-size: 1.5em;" id="systemStatus">IDLE</div>
                <p>当前状态</p>
            </div>
            <div class="card">
                <h3>处理延迟</h3>
                <div class="value" id="latency">0ms</div>
                <p>平均响应时间</p>
            </div>
        </div>

        <div class="card">
            <h3>📋 实时日志</h3>
            <div class="log-container" id="logContainer"></div>
        </div>
    </div>

    <script>
        let ws = null;
        let startTime = Date.now();
        let messageCount = 0;

        function connect() {
            ws = new WebSocket('ws://' + window.location.host + '/ws');
            
            ws.onopen = function() {
                document.getElementById('connectionStatus').textContent = '已连接';
                document.getElementById('connectionStatus').className = 'connection-status connected';
                addLog('system', 'WebSocket连接成功');
            };
            
            ws.onmessage = function(event) {
                const msg = JSON.parse(event.data);
                messageCount++;
                
                if (msg.event_type === 'stats_update') {
                    updateStats(msg.data);
                } else if (msg.event_type === 'log') {
                    addLog(msg.data.level || 'info', msg.data.message);
                } else {
                    addLog(msg.event_type, JSON.stringify(msg.data));
                }
                
                document.getElementById('messages').textContent = messageCount;
            };
            
            ws.onclose = function() {
                document.getElementById('connectionStatus').textContent = '未连接';
                document.getElementById('connectionStatus').className = 'connection-status disconnected';
                addLog('system', 'WebSocket连接断开，3秒后重连...');
                setTimeout(connect, 3000);
            };
            
            ws.onerror = function(error) {
                addLog('error', 'WebSocket错误: ' + error);
            };
        }

        function updateStats(data) {
            if (data.connections !== undefined) {
                document.getElementById('connections').textContent = data.connections;
            }
            if (data.status) {
                document.getElementById('systemStatus').textContent = data.status;
            }
            if (data.latency !== undefined) {
                document.getElementById('latency').textContent = data.latency + 'ms';
            }
        }

        function addLog(level, message) {
            const container = document.getElementById('logContainer');
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            
            const time = new Date().toLocaleTimeString();
            const color = {
                'info': '#00d4ff',
                'success': '#00ff88',
                'warning': '#ffaa00',
                'error': '#ff6464',
                'system': '#aaa'
            }[level] || '#ccc';
            
            entry.innerHTML = `
                <span class="time">[${time}]</span>
                <span class="event" style="color:${color}">${level.toUpperCase()}</span>
                <span class="data">${message}</span>
            `;
            
            container.appendChild(entry);
            container.scrollTop = container.scrollHeight;
            
            if (container.children.length > 100) {
                container.removeChild(container.firstChild);
            }
        }

        function startListening() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    action: 'start_listening'
                }));
                addLog('info', '开始监听...');
            }
        }

        function stopListening() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    action: 'stop_listening'
                }));
                addLog('info', '停止监听');
            }
        }

        function clearLogs() {
            document.getElementById('logContainer').innerHTML = '';
        }

        function updateUptime() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const hours = Math.floor(elapsed / 3600);
            const minutes = Math.floor((elapsed % 3600) / 60);
            const seconds = elapsed % 60;
            
            document.getElementById('uptime').textContent = 
                `${hours}h ${minutes}m ${seconds}s`;
        }

        setInterval(updateUptime, 1000);
        connect();
    </script>
</body>
</html>
        """
        return HTMLResponse(content=html_content)
    
    @app.post("/api/robot/command")
    async def robot_command(command: Dict[str, Any]):
        cmd_type = command.get("type")
        params = command.get("params", {})
        
        app.state.ws_manager.broadcast_to_subscribers(
            "robot_command",
            {
                "type": cmd_type,
                "params": params,
                "timestamp": datetime.now().isoformat()
            },
            source="api"
        )
        
        return {
            "success": True,
            "command": cmd_type,
            "params": params
        }
    
    @app.post("/api/agent/query")
    async def agent_query(query: Dict[str, Any]):
        question = query.get("question")
        mode = query.get("mode", "chat")
        
        app.state.ws_manager.broadcast_to_subscribers(
            "agent_query",
            {
                "question": question,
                "mode": mode,
                "timestamp": datetime.now().isoformat()
            },
            source="api"
        )
        
        return {
            "success": True,
            "question": question,
            "mode": mode,
            "message": "Query sent to agent"
        }


async def receive_messages(websocket: WebSocket, client_id: str, queue: asyncio.Queue):
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("action") == "subscribe":
                event_types = data.get("event_types", ["*"])
                app.state.ws_manager.subscribe(client_id, event_types)
            elif data.get("action") == "unsubscribe":
                event_types = data.get("event_types", ["*"])
                app.state.ws_manager.unsubscribe(client_id, event_types)
            elif data.get("action") == "start_listening":
                app.state.broadcaster.broadcast(
                    "start_listening",
                    {"client_id": client_id},
                    source="client"
                )
            elif data.get("action") == "stop_listening":
                app.state.broadcaster.broadcast(
                    "stop_listening",
                    {"client_id": client_id},
                    source="client"
                )
            else:
                app.state.broadcaster.broadcast(
                    "client_message",
                    {
                        "client_id": client_id,
                        "data": data
                    },
                    source="client"
                )
    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Error receiving messages: {e}")


async def send_messages(websocket: WebSocket, queue: asyncio.Queue):
    try:
        while True:
            message = await queue.get()
            await websocket.send_bytes(message)
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error sending messages: {e}")


def run_server(app: FastAPI, host: str = "0.0.0.0", port: int = 8000):
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )
