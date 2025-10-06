#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import argparse
from datetime import datetime, timezone, timedelta

def format_superk_alert(record):
    """スーパーカミオカンデのアラートを整形"""
    title = "【速報】スーパーカミオカンデ 超新星ニュートリノアラート"
    
    try:
        alert_time_str = record.get('alert_datetime', '不明')
        # ISO 8601形式の文字列をdatetimeオブジェクトに変換
        alert_dt_utc = datetime.fromisoformat(alert_time_str.replace('Z', '+00:00'))
        # JST（日本標準時）に変換
        jst = timezone(timedelta(hours=9))
        alert_time_jst = alert_dt_utc.astimezone(jst).strftime('%Y-%m-%d %H:%M:%S JST')

        neutrino_count = record.get('neutrino_count', 'N/A')
        
        body = (
            f"スーパーカミオカンデで超新星爆発に伴うニュートリノイベントの可能性があります。\n\n"
            f"■ 覚知日時:\n{alert_time_jst}\n\n"
            f"■ 検出ニュートリノ数:\n{neutrino_count} イベント\n\n"
            f"詳細はGCN速報を確認してください。"
        )
        return {"title": title, "body": body}
    except Exception as e:
        return format_fallback("Super-Kアラート整形エラー", record, e)


def format_heartbeat(record):
    """ハートビート（接続確認）を整形"""
    title = "GCNアラートシステム 接続確認"
    
    try:
        alert_time_str = record.get('alert_datetime', '不明')
        alert_dt_utc = datetime.fromisoformat(alert_time_str.replace('Z', '+00:00'))
        jst = timezone(timedelta(hours=9))
        alert_time_jst = alert_dt_utc.astimezone(jst).strftime('%Y-%m-%d %H:%M:%S JST')
        
        body = (
            f"これはGCN Kafkaストリームとの接続を確認するための定期的な通知です。\n\n"
            f"■ 送信時刻:\n{alert_time_jst}"
        )
        return {"title": title, "body": body}
    except Exception as e:
        return format_fallback("Heartbeat整形エラー", record, e)


def format_fallback(error_context, record, error=None):
    """その他のアラートやエラー発生時の汎用フォーマット"""
    title = f"GCN Alert: {error_context}"
    error_msg = f"Error: {error}\n\n" if error else ""
    body = (
        f"メッセージの自動生成に失敗したか、未対応のアラートです。\n"
        f"{error_msg}"
        f"詳細は以下のJSONデータを確認してください。\n\n"
        f"{json.dumps(record, indent=2, ensure_ascii=False)}"
    )
    return {"title": title, "body": body}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GCNアラートJSONを整形されたメッセージに変換します。')
    parser.add_argument('--json-string', required=True, help='GCNから受信した生のJSON文字列')
    parser.add_argument('--topic', required=True, help='Kafkaのトピック名')
    args = parser.parse_args()

    output = {}
    try:
        record_data = json.loads(args.json_string)
        
        # トピック名に応じて処理を分岐
        if 'superk.sn_alert' in args.topic:
            output = format_superk_alert(record_data)
        elif 'heartbeat' in args.topic:
            output = format_heartbeat(record_data)
        else:
            # 今後、'icecube'などの他のアラートについてもここに追加できます
            output = format_fallback(f"未対応トピック ({args.topic})", record_data)

    except json.JSONDecodeError as e:
        output = {
            "title": "GCN Alert: JSON解析エラー",
            "body": f"受信したデータのJSON形式が不正です。\nError: {e}\n\n" + args.json_string
        }
    except Exception as e:
        output = {
            "title": "GCN Alert: 不明なエラー",
            "body": f"メッセージ生成スクリプトで不明なエラーが発生しました。\nError: {e}\n\n" + args.json_string
        }
        
    # 結果をJSON形式で標準出力に出力（メインスクリプトがこれを受け取ります）
    print(json.dumps(output, ensure_ascii=False))