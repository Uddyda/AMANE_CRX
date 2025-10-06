#!/usr/bin/env node
// ファイル名: email/send_email.cjs

const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env') });
const nodemailer = require('nodemailer');

// コマンドライン引数をパースするヘルパー関数
function arg(name, def = '') {
  const i = process.argv.indexOf(`--${name}`);
  if (i !== -1 && process.argv[i + 1] && !process.argv[i + 1].startsWith('--')) {
    return process.argv[i + 1];
  }
  return def;
}

// ---- 引数と環境変数の読み込み ----

// <--- 変更点: 複数形 'RECIPIENT_EMAILS' を読み込む ---
const toAddrs = process.env.RECIPIENT_EMAILS; 
const subject = arg('subject', 'GCN Alert');
const message = arg('message', 'Alert triggered.');

// .envから認証情報を取得
const senderEmail = process.env.GMAIL_ADDRESS;
const appPassword = process.env.GMAIL_APP_PASSWORD;

if (!senderEmail || !appPassword) {
  console.error('エラー: 環境変数 GMAIL_ADDRESS または GMAIL_APP_PASSWORD が .env ファイルに設定されていません。');
  process.exit(1);
}
// <--- 変更点: toAddrsのチェックとエラーメッセージを複数形に修正 ---
if (!toAddrs) {
  console.error('エラー: .env ファイルに送信先メールアドレス(RECIPIENT_EMAILS)が設定されていません。');
  process.exit(1);
}

// ---- nodemailerの設定 ----

// Gmail用のトランスポーターを作成
const transporter = nodemailer.createTransport({
  host: 'smtp.gmail.com',
  port: 465,
  secure: true, // true for 465, false for other ports
  auth: {
    user: senderEmail,
    pass: appPassword,
  },
});

// ---- メイン処理 ----

async function main() {
  try {
    // メールを送信
    const info = await transporter.sendMail({
      from: `"GCN Alert System" <${senderEmail}>`, // 送信元名とアドレス
      to: toAddrs, // <--- 変更点: 複数の宛先が入った変数を渡す
      subject: subject, // 件名
      text: message, // プレーンテキストの本文
    });
    
    // <--- 変更点: ログメッセージを修正 ---
    console.log(`メール通知成功: [${toAddrs}] に送信しました (Message ID: ${info.messageId})`);
    process.exit(0);
  } catch (error) {
    console.error('メール通知失敗:', error.message);
    if (error.code === 'EAUTH') {
        console.error('ヒント: Gmailアドレスまたはアプリパスワードが間違っている可能性があります。');
    }
    process.exit(1);
  }
}

main();