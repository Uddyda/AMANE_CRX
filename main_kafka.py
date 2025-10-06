import subprocess
import json
import os
import sys
from gcn_kafka import Consumer
import pprint
import threading
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# -----------------------------------
# ★★★ 設定セクション ★★★
# -----------------------------------
# アラームの音量を設定 (0から100)
ALARM_VOLUME = 50 # 元のコードに合わせて音量を戻しました
# -----------------------------------

# -----------------------------------
# 環境変数から設定を読み込み、存在チェック
# -----------------------------------
KAFKA_CLIENT_ID = os.getenv("KAFKA_CLIENT_ID")
KAFKA_CLIENT_SECRET = os.getenv("KAFKA_CLIENT_SECRET")
BASE_PATH = os.getenv("BASE_PATH")

required_env_vars = {
    "KAFKA_CLIENT_ID": KAFKA_CLIENT_ID,
    "KAFKA_CLIENT_SECRET": KAFKA_CLIENT_SECRET,
    "BASE_PATH": BASE_PATH,
}
missing_vars = [key for key, value in required_env_vars.items() if value is None]
if missing_vars:
    print(f"エラー: 以下の必須環境変数が.envファイルに設定されていません: {', '.join(missing_vars)}")
    sys.exit(1)

# -----------------------------------
# サイレンを鳴らす関数（Mac用）
# -----------------------------------
def get_volume_and_mute():
    """現在の音量とミュート状態を取得"""
    vol = int(subprocess.check_output("osascript -e 'output volume of (get volume settings)'", shell=True).decode().strip())
    mute = subprocess.check_output("osascript -e 'output muted of (get volume settings)'", shell=True).decode().strip().lower()
    return vol, (mute == "true")

def set_volume_and_mute(volume, mute):
    """音量とミュート状態を設定"""
    os.system(f"osascript -e 'set volume output volume {volume}'")
    if mute:
        os.system("osascript -e 'set volume with output muted'")
    else:
        os.system("osascript -e 'set volume without output muted'")

def play_alarm():
    """サイレンをループ再生し、Enterキーで停止する"""
    original_volume, original_mute = get_volume_and_mute()
    print(f"元の音量: {original_volume}, ミュート: {original_mute}")
    try:
        alarm_file_path = os.path.join(BASE_PATH, "alarm.mp3")
        set_volume_and_mute(ALARM_VOLUME, False)
        command = f'while true; do afplay "{alarm_file_path}"; done'
        alarm_process = subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("\nアラート発生中... 停止するにはEnterキーを押してください。")
        input()
        alarm_process.terminate()
        alarm_process.wait()
    finally:
        set_volume_and_mute(original_volume, original_mute)
        print(f"音量を {original_volume} に戻しました (ミュート={original_mute})")

# -----------------------------------
# Kafka Consumerの設定
# -----------------------------------
consumer = Consumer(client_id=KAFKA_CLIENT_ID, client_secret=KAFKA_CLIENT_SECRET)
TARGET_TOPICS = ['gcn.notices.icecube.lvk_nu_track_search', 'gcn.notices.superk.sn_alert', 'gcn.heartbeat']

# -----------------------------------
# 各種スクリプトのパス設定
# -----------------------------------
SLACK_SCRIPT_PATH = os.path.join(BASE_PATH, 'slack', 'alert_to_slack.cjs')
PUSHOVER_SCRIPT_PATH = os.path.join(BASE_PATH, 'pushover', 'alert_to_pushover.cjs')
EMAIL_SCRIPT_PATH = os.path.join(BASE_PATH, 'email', 'alert_to_email.cjs')

### ★★★ 変更点 START (1/2) ★★★ ###
# メッセージ自動生成スクリプトのパスを追加
GENERATE_MESSAGE_SCRIPT_PATH = os.path.join(BASE_PATH, 'generate_message.py')
### ★★★ 変更点 END (1/2) ★★★ ###


print(f"以下のトピックを購読します: {TARGET_TOPICS}")
consumer.subscribe(TARGET_TOPICS)
print("アラート待機中...")

# -----------------------------------
# メインループ：GCNメッセージを受信
# -----------------------------------
while True:
    for message in consumer.consume(timeout=1):
        if message.error():
            print(f"Kafka Error: {message.error()}")
            continue

        print(f"\n---アラート受信！ topic: {message.topic()}---")

        ### ★★★ 変更点 START (2/2) ★★★ ###
        # --- メッセージ内容の準備 ---
        notification_title = f"GCN Alert: {message.topic()}" # デフォルトのタイトル
        notification_message = ""
        msg_json = {}

        try:
            msg_value = message.value().decode('utf-8')
            msg_json = json.loads(msg_value)
            # 安定性のため、まずは従来通りのメッセージをデフォルト値として設定
            notification_message = json.dumps(msg_json, indent=2, ensure_ascii=False)

            # --- メッセージの自動生成を試行 ---
            try:
                command = [
                    'python3', GENERATE_MESSAGE_SCRIPT_PATH,
                    '--json-string', msg_value,
                    '--topic', message.topic()
                ]
                result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
                generated_data = json.loads(result.stdout)
                
                # 成功した場合のみ、タイトルとメッセージを上書き
                notification_title = generated_data.get('title', notification_title)
                notification_message = generated_data.get('body', notification_message)
                
                print("\n" + "="*25 + " 自動生成メッセージ " + "="*25)
                print(f"タイトル: {notification_title}\n本文:\n{notification_message}")
                print("="*64)

            except Exception as e:
                # 自動生成に失敗しても処理は止めず、コンソールに警告を表示するのみ
                # 通知内容はデフォルト値（生のJSON）のまま処理が続行される
                print(f"\n### 警告: メッセージの自動生成に失敗しました。元のJSONデータで通知します。 ###")
                print(f"エラー詳細: {e}\n")

        except Exception as e:
            # KafkaメッセージのJSON解析自体に失敗した場合
            print(f"JSON解析エラー: {e}")
            notification_message = message.value().decode('utf-8')
            msg_json = {"error": "JSON parse error", "original_message": notification_message}
        
        ### ★★★ 変更点 END (2/2) ★★★ ###

        print("\n" + "="*25 + " 受信データ内容 (Raw JSON) " + "="*25)
        pprint.pprint(msg_json)
        print("="*64 + "\n")

        notification_title = f"GCN Alert: {message.topic()}"
        
        alarm_thread = threading.Thread(target=play_alarm)
        alarm_thread.start()

        # --- 以下、各種通知処理を即座に実行 ---
        # このセクションは一切変更ありません

        # 2. メール通知
        try:
            command = ['node', EMAIL_SCRIPT_PATH, '--subject', notification_title, '--message', notification_message]
            print(f"メール通知コマンド実行: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            print("メール通知成功:", result.stdout.strip())
        except FileNotFoundError:
            print(f"エラー: メール通知スクリプトが見つかりません: {EMAIL_SCRIPT_PATH}")
        except subprocess.CalledProcessError as e:
            print(f"メール通知失敗 (終了コード: {e.returncode}):\n標準出力: {e.stdout.strip()}\n標準エラー出力: {e.stderr.strip()}")

        # 3. Slack通知
        try:
            command = ['node', SLACK_SCRIPT_PATH, '--title', notification_title, '--message', notification_message]
            print(f"Slack通知コマンド実行: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            print("Slack通知成功:", result.stdout.strip())
        except FileNotFoundError:
            print(f"エラー: Slack通知スクリプトが見つかりません: {SLACK_SCRIPT_PATH}")
        except subprocess.CalledProcessError as e:
            print(f"Slack通知失敗 (終了コード: {e.returncode}):\n標準出力: {e.stdout.strip()}\n標準エラー出力: {e.stderr.strip()}")

        # 4. Pushover通知
        try:
            command = ['node', PUSHOVER_SCRIPT_PATH, '--title', notification_title, '--message', notification_message]
            print(f"Pushover通知コマンド実行: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            print("Pushover通知成功:", result.stdout.strip())
        except FileNotFoundError:
            print(f"エラー: Pushover通知スクリプトが見つかりません: {PUSHOVER_SCRIPT_PATH}")
        except subprocess.CalledProcessError as e:
            print(f"Pushover通知失敗 (終了コード: {e.returncode}):\n標準出力: {e.stdout.strip()}\n標準エラー出力: {e.stderr.strip()}")