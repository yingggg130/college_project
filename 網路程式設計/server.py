# server
import socket
import threading
import time
import json

# 遊戲設定
TCP_PORT = 5678
UDP_PORT = 5006
MAX_PLAYERS = 4
MAP_SIZE = (10, 10)
BOMB_TIMER = 3  # 炸彈爆炸前的秒數

# 執行緒安全的資料結構
game_lock = threading.Lock()
clients = {}            # player_id -> TCP socket
player_positions = {}   # player_id -> [row, col]
player_names = {}       # player_id -> 玩家名稱
player_colors = {}      # player_id -> 顏色
AVAILABLE_COLORS = ["blue", "green", "red", "orange", "purple", "brown"]

# UDP 廣播 socket
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
UDP_ADDR = ('255.255.255.255', UDP_PORT)

# 廣播 TCP 訊息給所有連線中的客戶端
def broadcast_tcp(message):
    for sock in list(clients.values()):
        try:
            sock.sendall(message.encode())
        except:
            pass

# 透過 TCP 廣播目前遊戲狀態（以 JSON 格式）
def broadcast_state():
    data = {
        "type": "update",
        "positions": player_positions,
        "names": player_names,
        "colors": player_colors
    }
    broadcast_tcp(json.dumps(data))

# 透過 TCP 廣播聊天訊息
def broadcast_chat(text):
    data = {"type": "chat", "player": "Server", "message": text}
    broadcast_tcp(json.dumps(data))

# 處理炸彈邏輯：包含 UDP、TCP 廣播與淘汰處理
def handle_bomb(r, c):
    # 使用 UDP 廣播炸彈被放置（即時通知）
    udp_sock.sendto(f"BOMB_PLANTED at ({r},{c})".encode(), UDP_ADDR)
    # 使用 TCP 廣播炸彈放置事件
    broadcast_tcp(json.dumps({"type": "bomb_placed", "row": r, "col": c}))
    # 等待炸彈爆炸
    time.sleep(BOMB_TIMER)
    eliminated = []
    eliminated_sockets = {}

    with game_lock:
        # 計算炸彈爆炸範圍
        blast = {(r, c)}
        for d in range(1, 4):
            blast.update({(r+d, c), (r-d, c), (r, c+d), (r, c-d)})

        # 找出被炸到的玩家
        for pid, pos in list(player_positions.items()):
            if tuple(pos) in blast:
                eliminated.append(pid)
                eliminated_sockets[pid] = clients.get(pid)

        # 廣播爆炸事件
        broadcast_tcp(json.dumps({
            "type": "explosion",
            "row": r,
            "col": c,
            "eliminated": eliminated
        }))

        # 廣播淘汰通知（聊天訊息）
        for pid in eliminated:
            name = player_names.get(pid, pid)
            broadcast_chat(f"玩家 {name} 被炸彈淘汰。")
    time.sleep(0.5)
    # 向被淘汰的玩家發送淘汰訊息，並等待一段時間再關閉連線
    for pid in eliminated:
        sock = eliminated_sockets.get(pid)
        if sock:
            try:
                # 以 JSON 格式傳送淘汰訊息供 client 處理
                elimination_msg = json.dumps({"type": "eliminated", "message": "你被炸彈淘汰了！"})
                sock.sendall(elimination_msg.encode())
                # 給 client 一點時間處理訊息
                time.sleep(0.5)
            except:
                pass
    time.sleep(0.5)
    # 將被淘汰的玩家從遊戲狀態中移除
    with game_lock:
        for pid in eliminated:
            sock = clients.get(pid)
            if sock:
                try:
                    sock.close()
                except:
                    pass
            clients.pop(pid, None)
            player_positions.pop(pid, None)
            player_names.pop(pid, None)
            player_colors.pop(pid, None)

    # 最後再更新一次遊戲狀態
    broadcast_state()

# 處理每個 TCP 客戶端連線
def handle_client(sock, addr):
    pid = f"P{len(clients) + 1}"
    # 接收 NAME 指令
    try:
        raw = sock.recv(1024).decode().strip()
        if not raw.startswith("NAME "):
            sock.close()
            return
        name = raw[5:][:5]
        color = AVAILABLE_COLORS[len(clients) % len(AVAILABLE_COLORS)]

        with game_lock:
            clients[pid] = sock
            player_positions[pid] = [0, 0]
            player_names[pid] = name
            player_colors[pid] = color

        # 傳送歡迎訊息
        sock.sendall(f"WELCOME {pid}".encode())
        broadcast_chat(f"玩家 {name}({pid}) 加入遊戲。")
        broadcast_state()

        while True:
            data = sock.recv(1024)
            if not data:
                break
            msg = data.decode().strip()

            if msg.startswith("CHAT "):
                text = msg[5:]
                broadcast_chat(f"{name}: {text}")
            elif msg.startswith("MOVE "):
                _, direction = msg.split()
                with game_lock:
                    if pid in player_positions:  # 確認玩家仍在線上
                        r, c = player_positions[pid]
                        if direction == "UP":    r = max(0, r-1)
                        elif direction == "DOWN":r = min(MAP_SIZE[0]-1, r+1)
                        elif direction == "LEFT":c = max(0, c-1)
                        elif direction == "RIGHT":c = min(MAP_SIZE[1]-1, c+1)
                        player_positions[pid] = [r, c]
                broadcast_state()
            elif msg == "BOMB":
                with game_lock:
                    if pid in player_positions:  # 確認玩家仍在線上
                        r, c = player_positions[pid]
                        threading.Thread(target=handle_bomb, args=(r, c), daemon=True).start()

    except Exception as e:
        print(f"Client {pid} error: {e}")
    finally:
        with game_lock:
            if pid in clients:
                clients.pop(pid, None)
                player_positions.pop(pid, None)
                name = player_names.pop(pid, None)
                player_colors.pop(pid, None)
                if name:
                    broadcast_chat(f"玩家 {name}({pid}) 離開。")
                broadcast_state()
        try:
            sock.close()
        except:
            pass

# 主伺服器迴圈
if __name__ == '__main__':
    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # 允許重複使用 port
    tcp_server.bind(("", TCP_PORT))
    tcp_server.listen(MAX_PLAYERS)
    print(f"TCP Server on {TCP_PORT}, UDP broadcast on {UDP_PORT}")
    try:
        while True:
            conn, addr = tcp_server.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("Server shutting down.")
    finally:
        tcp_server.close()
