#__future__啟用 Python 的未來特性，確保兼容性（如在舊版 Python 中使用新版功能）。
from __future__ import absolute_import #強制使用絕對匯入
from __future__ import division
from __future__ import print_function #讓 print() 成為一個函數


import time #處理時間相關操作
import numpy as np #處理數值運算
import cv2 #OpenCV，用於影像處理。
import threading #用於多執行緒
from tflite_runtime.interpreter import Interpreter #TensorFlow Lite 解譯器，用於模型推論。
from gtts import gTTS #Google Text-to-Speech，用於生成語音。
from playsound import playsound #播放音檔
import random #生成隨機數

DELAY_TIME = 3.0 #延遲時間（秒數），控制語音播放的頻率。

#從指定檔案路徑讀取標籤
def load_labels(path):
    with open(path, 'r', encoding='utf-8') as f:
        return {i: line.strip() for i, line in enumerate(f.readlines())}

#將影像數據加載到 TensorFlow Lite 解譯器的輸入張量。
def set_input_tensor(interpreter, image):
  tensor_index = interpreter.get_input_details()[0]['index']
  input_tensor = interpreter.tensor(tensor_index)()[0]
  input_tensor[:, :] = image

#影像分類
def classify_image(interpreter, image, top_k=1):
  """Returns a sorted array of classification results."""
  set_input_tensor(interpreter, image)
  interpreter.invoke()
  output_details = interpreter.get_output_details()[0]
  output = np.squeeze(interpreter.get_tensor(output_details['index']))
  # 若模型使用量化（uint8），則進行反量化。
  if output_details['dtype'] == np.uint8:
    scale, zero_point = output_details['quantization']
    output = scale * (output - zero_point)
  ordered = np.argpartition(-output, top_k)
  return [(i, output[i]) for i in ordered[:top_k]]

#依序播放音效
def voice_play(voice_files):
    for voice_file in voice_files:
        playsound(voice_file)

#繪製背景文字
def draw_text_with_background(image, text, position, font, font_scale, text_color, bg_color, thickness):
    # 計算文字的尺寸
    text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
    text_width, text_height = text_size
    # 設置文字背景矩形框
    top_left = (position[0]-8, position[1] - text_height - 8)
    bottom_right = (position[0]+8 + text_width, position[1] + 12)
    cv2.rectangle(image, top_left, bottom_right, bg_color, 3)  # -1 表示填滿矩形
    # 繪製文字
    cv2.putText(image, text, position, font, font_scale, text_color, thickness)

#添加小圖標
def add_icon(image, icon_path, position, size=(150, 150)):
    """
    在影像上繪製小圖標。
    :param image: 目標影像
    :param icon_path: 小圖標的檔案路徑
    :param position: 小圖標的繪製位置 (左上角座標)
    :param size: 小圖標的縮放大小，預設為 (150, 150)
    """
    try:
        icon = cv2.imread(icon_path, cv2.IMREAD_UNCHANGED)
        if icon is None:
            print(f"無法加載小圖片：{icon_path}")
            return
        icon = cv2.resize(icon, size, interpolation=cv2.INTER_AREA)
        # 處理透明背景
        if icon.shape[2] == 4:  # 如果有 alpha 通道
            alpha_channel = icon[:, :, 3] / 255.0
            for c in range(3):  # 對 RGB 通道進行處理
                image[position[1]:position[1] + size[1], position[0]:position[0] + size[0], c] = \
                    image[position[1]:position[1] + size[1], position[0]:position[0] + size[0], c] * (1 - alpha_channel) + \
                    icon[:, :, c] * alpha_channel
        else:  # 無透明背景，直接覆蓋
            image[position[1]:position[1] + size[1], position[0]:position[0] + size[0]] = icon
    except Exception as e:
        print(f"添加小圖片時發生錯誤：{e}")

#學習模式，拿圖系統辨認
def run_mode1(interpreter, labels, zh):
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    eye_protection = False  # 護眼濾鏡狀態
    key_detect = 0
    times = 1
    t_flag = 0
    PRE_TIME = time.time()
    while key_detect == 0:
        ret, image_src = cap.read()
        frame_width = image_src.shape[1]
        frame_height = image_src.shape[0]
        cut_d = int((frame_width - frame_height) / 2)
        crop_img = image_src[0:frame_height, cut_d:(cut_d + frame_height)]
        image = cv2.resize(crop_img, (224, 224), interpolation=cv2.INTER_AREA)
        if eye_protection:
            crop_img = cv2.addWeighted(crop_img, 0.8, np.full_like(crop_img, (30, 90, 140)), 0.2, 0)
        start_time = time.time()
        if times == 1:
            results = classify_image(interpreter, image)
            elapsed_ms = (time.time() - start_time) * 1000
            label_id, prob = results[0]
            print(labels[label_id], prob)
        # 顯示辨識文字
        cv2.putText(crop_img, labels[label_id] + " " + str(round(prob, 2)),
                    (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 6, cv2.LINE_AA)
        cv2.putText(crop_img, labels[label_id] + " " + str(round(prob, 2)),
                    (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA)
        # 添加對應的小圖標
        icon_path = f"C:/VISION_VOICE/icons/{label_id}.png"  # 假設圖標命名與 labels 相對應
        add_icon(crop_img, icon_path, (5, 40))
        if ((labels[label_id] != '5 others') and (t_flag == 0) and (time.time() - PRE_TIME > DELAY_TIME)):
            PRE_TIME = time.time()
            # 播放語音
            sound_file_en = f'C:/VISION_VOICE/label_en_{label_id}.mp3'
            sound_file_zh = f'C:/VISION_VOICE/label_zh_{label_id}.mp3'
            voice_files = [sound_file_en, sound_file_zh]
            t_voice_play = threading.Thread(target=voice_play, args=(voice_files,))
            t_voice_play.start()
        if t_flag == 1:
            t_voice_play.join()
            t_flag = 0
        times = times + 1
        if times > 10:
            times = 1
        cv2.imshow('Detecting....', crop_img)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            key_detect = 1
        elif key == ord('w'):
            eye_protection = not eye_protection
    cap.release()
    cv2.destroyAllWindows()

#問答模式，系統出題目，使用者回答
def run_mode2(interpreter, labels):
    # 添加 eye_protection 變數，並在循環中檢測 'w' 鍵切換護眼濾鏡
    eye_protection = False  # 護眼濾鏡狀態
    CA=0
    # 開啟攝像頭
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    key_detect = 0
    times = 1
    played = False  # 控制題目語音播放
    answer_played = False  # 控制答案語音播放
    # 初始化題目
    random_word_id = random.randint(0, 4)
    word = labels[random_word_id]
    PRE_TIME = time.time()
    def play_sound(file):
        """播放音效的輔助函式，確保單一執行緒執行"""
        try:
            playsound(file)
        except Exception as e:
            print(f"播放音效時發生錯誤：{e}")
    while key_detect == 0:
        ret, image_src = cap.read()
        if not ret:
            print("無法啟動鏡頭，請檢查設備。")
            break
        frame_width = image_src.shape[1]
        frame_height = image_src.shape[0]
        cut_d = int((frame_width - frame_height) / 2)
        crop_img = image_src[0:frame_height, cut_d:(cut_d + frame_height)]
        image = cv2.resize(crop_img, (224, 224), interpolation=cv2.INTER_AREA)
        # 檢查是否需要啟用護眼濾鏡
        if eye_protection:
            crop_img = cv2.addWeighted(crop_img, 0.8, np.full_like(crop_img, (30, 90, 140)), 0.2, 0)
        if times == 1:
            results = classify_image(interpreter, image)
            label_id, prob = results[0]
            print(f"偵測到：{labels[label_id]} 機率：{prob}")
            print(f"目標單字：{word}")
        # 顯示提示文字
        cv2.putText(crop_img,"Question: "+ word + " " ,(5, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (250, 206, 135), 7, cv2.LINE_AA)
        cv2.putText(crop_img, "Question: "+word + " " ,
                    (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(crop_img, "Correct Answer: "+str(CA) ,(5, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (152, 251, 152), 7, cv2.LINE_AA)
        cv2.putText(crop_img, "Correct Answer: "+str(CA) ,(5, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA)
        # 判斷是否答對
        if labels[label_id] == word:
            if not answer_played:
                print('答對！播放答案語音。')
                CA+=1
                # 播放答案語音（英文+中文）
                sound_file_en = f'C:/VISION_VOICE/label_en_{random_word_id}.mp3'
                sound_file_zh = f'C:/VISION_VOICE/label_zh_{random_word_id}.mp3'
                voice_files = [sound_file_en, sound_file_zh]
                t_voice_play = threading.Thread(target=voice_play, args=(voice_files,))
                t_voice_play.start()
                t_voice_play.join()
                # 依次播放英文和中文
                answer_played = True  # 確保答案語音只播放一次
            previous_word_id = random_word_id  # 儲存上一題索引
            # 更新題目
            if answer_played:
                time.sleep(1)  # 停頓後更換題目
                random_word_id = random.randint(0, 4)
                while random_word_id == previous_word_id:
                    random_word_id = random.randint(0, 4)
                word = labels[random_word_id]
                print(f"新題目：{word}")
                played = False  # 重置題目語音播放狀態
                answer_played = False  # 重置答案播放狀態
                PRE_TIME = time.time()
        # 題目語音（只播放英文）
        if not played and time.time() - PRE_TIME > 1:
            sound_file_en = f'C:/VISION_VOICE/label_en_{random_word_id}.mp3'
            t = threading.Thread(target=play_sound, args=(sound_file_en,))
            t.start()
            played = True  # 確保題目語音只播放一次
        times += 1
        if times > 8:
            times = 1
        cv2.imshow('Detecting....', crop_img)
        # 檢測按鍵
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            key_detect = 1
        elif key == ord('w'):
            eye_protection = not eye_protection  # 切換護眼濾鏡狀態
    cap.release()
    cv2.destroyAllWindows()

#模式選擇畫面
def show_mode_selection():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    mode = None
    while True:
        ret, frame = cap.read()
        if not ret:
            print("無法啟動鏡頭，請檢查設備。")
            break
        frame = np.zeros((300, 600, 3), dtype=np.uint8)  # 創建一個黑色畫布
        frame[:] = [85, 80, 76]
        draw_text_with_background(frame, "Bilingual Learning Partner", (50, 65),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), (187, 195, 202), 2)
        draw_text_with_background(frame, "Press '1' for Mode 1", (50, 125),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), (187, 195, 202), 2)
        draw_text_with_background(frame, "Press '2' for Mode 2", (50, 185),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), (187, 195, 202), 2)
        draw_text_with_background(frame, "Press 'q' to Quit", (50, 245),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), (187, 195, 202), 2)
        cv2.imshow("Welcome", frame)
        # 等待按鍵輸入選擇模式
        key = cv2.waitKey(1) & 0xFF
        if key == ord('1'):  # 選擇 Mode 1
            mode = 1
            break
        elif key == ord('2'):  # 選擇 Mode 2
            mode = 2
            break
        elif key == ord('q'):  # 退出程式
            cap.release()
            cv2.destroyAllWindows()
            return
    cv2.destroyWindow("Welcome")
    return mode


def main():
    model_file = 'C:/VISION_VOICE/model_4/model.tflite'
    labels_file = 'C:/VISION_VOICE/model_4/labels.txt'
    zh_file = 'C:/VISION_VOICE/zh.txt'
    labels = load_labels(labels_file)
    zh = load_labels(zh_file)

    # 生成語音檔案，先用英文語音，然後用中文語音
    for i in range(len(labels)):
      text_list = labels[i].split(' ')
      text_zh = zh[i].split(' ')
      # 英文語音
      speech_en = gTTS(text=text_list[1], lang='en', slow=False)
      speech_en_file = 'label_en_' + str(i) + '.mp3'
      speech_en.save(speech_en_file)  
      # 中文語音
      speech_zh = gTTS(text=text_zh[0], lang='zh-tw', slow=False)
      speech_zh_file = 'label_zh_' + str(i) + '.mp3'
      speech_zh.save(speech_zh_file)

    interpreter = Interpreter(model_file)
    interpreter.allocate_tensors()

    mode = show_mode_selection()

    if mode == 1:
        run_mode1(interpreter, labels, zh)
    elif mode == 2:
        run_mode2(interpreter, labels)
    else:
        print("No valid mode selected.")

if __name__ == '__main__':
    main()
