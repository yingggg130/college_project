# client
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext
import socket
import threading
import json
import time

# 設定
TCP_HOST = '127.0.0.1'
TCP_PORT = 5678
UDP_PORT = 5006
GRID_SIZE = 10
CELL_SIZE = 40
BOMB_DISPLAY = 3

class BombGameClient:
    def __init__(self, master):
        self.master = master
        # 視窗標題與圖示
        try:
            icon = tk.PhotoImage(file="icon.png")
            master.iconphoto(False, icon)
        except:
            pass
        master.title("炸雞全家餐")

        # 地圖畫布
        self.canvas = tk.Canvas(master, width=GRID_SIZE*CELL_SIZE,
                                height=GRID_SIZE*CELL_SIZE)
        self.canvas.grid(row=0, column=0, rowspan=2)
        self.canvas.bind('<KeyPress>', self.handle_key)
        self.canvas.bind('<Button-1>', lambda e: self.canvas.focus_set())

        # 聊天介面
        self.chat_box = scrolledtext.ScrolledText(master, state='disabled',
                                                  width=30, height=15)
        self.chat_box.grid(row=0, column=1)
        self.chat_entry = tk.Entry(master, width=25)
        self.chat_entry.grid(row=1, column=1, sticky='w')
        self.chat_entry.bind('<Return>', lambda e: self.send_chat())
        tk.Button(master, text="送出", command=self.send_chat).grid(row=1, column=1, sticky='e')

        # 載入圖示
        try:
            self.bomb_img = tk.PhotoImage(file="bomb.png")
        except:
            # 若無圖示則建立簡單的炸彈圖樣
            self.bomb_img = None
        self.icons = {}

        # 狀態資訊
        self.pid = None
        self.positions = {}
        self.names = {}
        self.colors = {}
        self.bombs = []  # (r,c,t)
        self.running = True
        self.eliminated = False

        # 建立 TCP 連線
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((TCP_HOST, TCP_PORT))
            
            name = simpledialog.askstring("暱稱", "請輸入名字 (最多5字)", parent=master)
            if not name:
                master.destroy()
                return
            self.name = name[:5]
            self.sock.sendall(f"NAME {self.name}".encode())

            # 啟動執行緒
            threading.Thread(target=self.receive_tcp, daemon=True).start()
            threading.Thread(target=self.receive_udp, daemon=True).start()
            master.after(100, lambda: self.canvas.focus_set())
            
        except Exception as e:
            messagebox.showerror("連接錯誤", f"無法連接到服務器: {e}")
            master.destroy()

    def handle_key(self, event):
        if not self.running or self.eliminated or event.widget != self.canvas or not self.pid:
            return
        key = event.keysym
        if key in ('Up', 'Down', 'Left', 'Right'):
            try:
                self.sock.sendall(f"MOVE {key.upper()}".encode())
            except:
                pass
        elif key == 'space':
            try:
                self.sock.sendall(b"BOMB")
            except:
                pass

    def send_chat(self):
        if not self.running or self.eliminated:
            return
        msg = self.chat_entry.get().strip()
        if msg:
            try:
                self.sock.sendall(f"CHAT {msg}".encode())
            except:
                pass
        self.chat_entry.delete(0, tk.END)
        self.canvas.focus_set()

    def receive_tcp(self):
        try:
            while self.running:
                raw = self.sock.recv(4096)
                if not raw:
                    break
                    
                # 處理歡迎訊息
                if raw.startswith(b"WELCOME"):
                    self.pid = raw.decode().split()[1]
                    continue
                
                # 處理舊版的淘汰訊息
                if raw.strip() == b"YOU_DIED":
                    if not self.eliminated:
                        self.eliminated = True
                        self.master.after(0, lambda: self.show_elimination_message("你被淘汰了！"))
                    return
                
                # 處理 JSON 訊息
                try:
                    data = json.loads(raw.decode())
                except:
                    continue
                    
                msg_type = data.get('type')
                
                if msg_type == 'update':
                    self.positions = data['positions']
                    self.names = data['names']
                    self.colors = data['colors']
                    self.master.after(0, self.update_icons)
                    self.master.after(0, self.draw_board)
                    
                elif msg_type == 'bomb_placed':
                    self.bombs.append((data['row'], data['col'], time.time()))
                    self.master.after(0, self.draw_board)
                    
                elif msg_type == 'explosion':
                    self.master.after(0, self.draw_board)
                    # 檢查是否為被炸淘汰的玩家
                    eliminated_players = data.get('eliminated', [])
                    print(f"爆炸事件: 淘汰玩家 {eliminated_players}, 我的ID: {self.pid}")  # 調試信息
                    if self.pid in eliminated_players:
                        if not self.eliminated:
                            print("我被淘汰了！觸發通知...")  # 調試信息
                            self.eliminated = True
                            self.master.after(0, lambda: self.show_elimination_message("你被炸彈淘汰了！"))
                    
                elif msg_type == 'eliminated':
                    print(f"收到淘汰消息: {data}")  # 調試信息
                    if not self.eliminated:
                        print("處理淘汰消息...")  # 調試信息
                        self.eliminated = True
                        message = data.get('message', '你被淘汰了！')
                        self.master.after(0, lambda: self.show_elimination_message(message))
                    
                elif msg_type == 'chat':
                    player = data['player']
                    message = data['message']
                    self.master.after(0, lambda p=player, m=message: self.append_chat(p, m))
                    
        except Exception as e:
            if self.running and not self.eliminated:
                self.master.after(0, lambda: self.append_chat('系統', f'連接中斷: {e}'))

    def show_elimination_message(self, message):
        """顯示淘汰訊息"""
        print(f"show_elimination_message 被調用: {message}")  # 調試信息
        if self.eliminated:
            print("顯示淘汰彈跳視窗...")  # 調試信息
            self.show_elimination_popup(message)
            self.canvas.config(bg='lightgray')  # 改變背景色
            self.append_chat('系統', '你已被淘汰，但可以繼續觀戰和聊天。')
        else:
            print("eliminated 狀態為 False，不顯示彈跳視窗")  # 調試信息
    
    def show_elimination_popup(self, message):
        """顯示彈跳效果的淘汰視窗"""
        print("正在創建淘汰彈跳視窗...")  # 調試信息
        
        # 顯示基本淘汰對話框
        messagebox.showwarning("💥 遊戲結束 💥", f"{message}\n\n你已被淘汰！")
        
        # 建立自訂彈跳視窗
        popup = tk.Toplevel(self.master)
        popup.title("💥 GAME OVER 💥")
        popup.geometry("400x250")
        popup.resizable(False, False)
        popup.configure(bg='red')
        
        # 置中視窗
        popup.transient(self.master)
        popup.grab_set()
        
        try:
            # 標題
            title_label = tk.Label(popup, text="💥 你被淘汰了！ 💥", 
                                  font=('Arial', 20, 'bold'), 
                                  fg='white', bg='red')
            title_label.pack(pady=20)
            
            # 淘汰訊息
            message_label = tk.Label(popup, text=message, 
                                    font=('Arial', 14), 
                                    fg='white', bg='red')
            message_label.pack(pady=10)
            
            # 按鈕框架
            button_frame = tk.Frame(popup, bg='red')
            button_frame.pack(pady=20)
            
            # 繼續觀戰按鈕
            continue_btn = tk.Button(button_frame, text="繼續觀戰", 
                                   font=('Arial', 12, 'bold'),
                                   bg='orange', fg='white',
                                   command=popup.destroy)
            continue_btn.pack(side=tk.LEFT, padx=10)
            
            # 退出遊戲按鈕
            quit_btn = tk.Button(button_frame, text="退出遊戲", 
                               font=('Arial', 12, 'bold'),
                               bg='darkred', fg='white',
                               command=self.quit_game)
            quit_btn.pack(side=tk.LEFT, padx=10)
            
            # 加入動畫效果
            self.animate_popup(popup)
            
        except Exception as e:
            print(f"創建彈跳視窗時出錯: {e}")
            popup.destroy()
    
    def animate_popup(self, popup):
        """彈跳動畫效果"""
        original_geometry = popup.geometry()
        
        # 彈跳尺寸序列
        bounce_sequence = [
            ("350x200", 100),
            ("450x280", 100),
            ("380x230", 100),
            ("420x260", 100),
            ("400x250", 100),
        ]
        
        def bounce_step(step=0):
            if step < len(bounce_sequence):
                size, delay = bounce_sequence[step]
                popup.geometry(size)
                popup.after(delay, lambda: bounce_step(step + 1))
        
        bounce_step()
        self.flash_popup(popup)
    
    def flash_popup(self, popup, flash_count=0):
        """視窗閃爍效果"""
        if flash_count < 6:
            current_bg = popup.cget('bg')
            new_bg = 'darkred' if current_bg == 'red' else 'red'
            popup.configure(bg=new_bg)
            for child in popup.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=new_bg)
                elif isinstance(child, tk.Frame):
                    child.configure(bg=new_bg)
            popup.after(200, lambda: self.flash_popup(popup, flash_count + 1))
    
    def quit_game(self):
        """離開遊戲"""
        self.running = False
        try:
            self.sock.close()
        except:
            pass
        self.master.quit()
        self.master.destroy()

    def receive_udp(self):
        try:
            us = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            us.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            us.bind(("", UDP_PORT))
            while self.running:
                data, _ = us.recvfrom(1024)
                message = data.decode()
                self.master.after(0, lambda m=message: self.append_chat('UDP', m))
        except Exception as e:
            if self.running:
                self.master.after(0, lambda: self.append_chat('系統', f'UDP連接錯誤: {e}'))

    def update_icons(self):
        for pid, color in self.colors.items():
            if pid not in self.icons:
                try:
                    img = tk.PhotoImage(file=f"icons/{color}.png")
                except:
                    img = None
                self.icons[pid] = img

    def draw_board(self):
        now = time.time()
        self.canvas.delete('all')
        
        # 畫出格子
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                self.canvas.create_rectangle(c*CELL_SIZE, r*CELL_SIZE, 
                                           (c+1)*CELL_SIZE, (r+1)*CELL_SIZE, 
                                           outline='gray')
        
        # 畫出炸彈（清除過期炸彈）
        self.bombs = [(r, c, t) for r, c, t in self.bombs if now - t < BOMB_DISPLAY]
        for r, c, _ in self.bombs:
            x, y = c*CELL_SIZE + CELL_SIZE//2, r*CELL_SIZE + CELL_SIZE//2
            if self.bomb_img:
                self.canvas.create_image(x, y, image=self.bomb_img)
            else:
                # 沒圖示則用黑圓表示
                self.canvas.create_oval(x-10, y-10, x+10, y+10, fill='black')
                self.canvas.create_text(x, y, text='💣', font=('Arial', 12))
        
        # 畫出玩家
        for pid, (r, c) in self.positions.items():
            x, y = c*CELL_SIZE + CELL_SIZE//2, r*CELL_SIZE + CELL_SIZE//2
            icon = self.icons.get(pid)
            
            if icon:
                self.canvas.create_image(x, y, image=icon)
            else:
                # 畫有名字的彩色圓形
                color = self.colors.get(pid, 'black')
                self.canvas.create_oval(x-15, y-15, x+15, y+15, fill=color)
                name = self.names.get(pid, pid)
                self.canvas.create_text(x, y, text=name, fill='white', 
                                      font=('Arial', 10, 'bold'))
            
            # 標示自己的玩家
            if pid == self.pid and not self.eliminated:
                self.canvas.create_rectangle(x-20, y-20, x+20, y+20, 
                                           outline='yellow', width=3)
        
        self.canvas.focus_set()

    def append_chat(self, pid, text):
        self.chat_box.config(state='normal')
        self.chat_box.insert(tk.END, f"{pid}: {text}\n")
        self.chat_box.yview(tk.END)
        self.chat_box.config(state='disabled')

    def __del__(self):
        try:
            if hasattr(self, 'sock'):
                self.sock.close()
        except:
            pass

if __name__ == '__main__':
    root = tk.Tk()
    try:
        game = BombGameClient(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("錯誤", f"遊戲啟動失敗: {e}")
    finally:
        try:
            root.destroy()
        except:
            pass
