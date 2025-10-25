# はじめに

この記事はVibeコーディング未経験者の最初の一歩として、AIコーディングエージェント Gemini CLI を使ってドローン制御アプリを開発するハンズオン資料です。
> **Vibeコーディングとは**  
> AIに主導権を委ね、自然言語での対話を通じてソフトウェア開発を行う手法です。AIがコードの補完や生成を担うことで、アイデアを迅速に形にしやすくなります。生産性への影響は、プロジェクトの規模や性質によって異なります。

# 事前準備  

下記ツール導入、アカウント作成を行っておくこと。すでにある場合はスキップ可。  

## Vibeコーディング用
| No. | ツール名 | 説明 | コマンド (PowerShell) |
| --- | --- | --- | --- |
| 1 | [Googleアカウント](https://accounts.google.com/signup) | Gemini CLI認証用 | |
| 2 | [Node.js](https://nodejs.org/en/) | Gemini CLI実行環境 | `winget install OpenJS.NodeJS` |
| 3 | [VS Code](https://code.visualstudio.com/) | ソースコードエディタ | `winget install Microsoft.VisualStudioCode` |
| 4 | [Gemini CLI](https://www.npmjs.com/package/@google/gemini-cli) | Google製 AIコーディングエージェント | `npm install -g @google/gemini-cli` |

> ⚠️**CAUTION**  
> グローバルインストール (`-g`) を行うため、管理者権限が必要な場合があります。

## ドローン開発用
| No. | ツール名 | 説明 | コマンド (PowerShell) |
| --- | --- | --- | --- |
| 1 | [Python](https://www.python.org/downloads/) | Pymavlink実行環境, v3.12以上推奨 | `winget install Python.Python.3.13` |
| 2 | [Pymavlink](https://pypi.org/project/pymavlink/) | MAVLink通信用Pythonライブラリ | `pip install pymavlink` |
| 3 | [Mission Planner](https://ardupilot.org/planner/docs/mission-planner-installation.html) | ArduPilot用地上管制ソフト、シミュレーション環境 | |


# CUI版ドローン制御アプリ開発
## Gemini CLI起動
1. 任意の名前のフォルダ(例:`vibe-coding-handson`)を作る。
1. VS Code を起動してメニュー `ファイル` -> `フォルダーを開く` から作成したフォルダを開く。
1. メニュー `ターミinal` -> `新しいターミナル` からターミナルを起動して、 `gemini` コマンドを実行する。
    * 初回起動時に認証を求めれるので、`1. Login with Google` を選択して認証を行う。
1. 下記画面が表示されたらOK。`Type your message or @path/to/file` 欄にプロンプトを入力する。

```
 ███            █████████  ██████████ ██████   ██████ █████ ██████   █████ █████
░░░███         ███░░░░░███░░███░░░░░█░░██████ ██████ ░░███ ░░██████ ░░███ ░░███
  ░░░███      ███     ░░░  ░███  █ ░  ░███░█████░███  ░███  ░███░███ ░███  ░███
    ░░░███   ░███          ░██████    ░███░░███ ░███  ░███  ░███░░███░███  ░███
     ███░    ░███    █████ ░███░░█    ░███ ░░░  ░███  ░███  ░███ ░░██████  ░███
   ███░      ░░███  ░░███  ░███ ░   █ ░███      ░███  ░███  ░███  ░░█████  ░███
 ███░         ░░█████████  ██████████ █████     █████ █████ █████  ░░█████ █████
░░░            ░░░░░░░░░  ░░░░░░░░░░ ░░░░░     ░░░░░ ░░░░░ ░░░░░    ░░░░░ ░░░░░

Tips for getting started:
1. ...
2. ...

╭───────────────────────────────────────────────────────────────────────────────╮
│ >   Type your message or @path/to/file                                        │
╰───────────────────────────────────────────────────────────────────────────────╯
```

## 要件定義
1. Gemini CLIに下記プロンプトを入力して、要件定義書作成を指示する。
    ```powershell
    ドローン制御アプリの要件定義書を drone-app/REQUIREMENTS.md として作成してください。Pythonを使い、Pymavlinkライブラリを使用してドローンと通信します。アーム（モーター開始）、離陸、座標指定移動、着陸をコマンド実行できる機能を実装してください。Mission Plannerのシミュレーション環境（接続先:tcp:127.0.0.1:5762）で動作確認を行います。
    ```
    > 💡**TIPS**  
    > AIの作業を止めたい場合は`ESC`キーをクリックします。
1. 下記のようにAIから判断を求められた場合、内容を確認し回答する。
    ```powershell
    Allow execution?

    ○ Yes, allow once
    ● Yes, allow always "..."
    ○ No (esc)
    ```
    > 💡**TIPS**  
    > `Yes, allow always..` を選択すると、同一セッション内の同様操作は自動実行されます。
6. AIの作業が完了したら、`drone-app/REQUIREMENTS.md` が作成されていることを確認する。必要に応じて手動で編集するか、AIに修正依頼する。
   * プロンプト例：`シミュレーション環境のみで動作すれば十分です。`, `実機での動作は考慮不要です。`

## 依存ライブラリ定義
1. Gemini CLIに下記プロンプトを入力して、依存ライブラリを定義したファイルを作成する。
    ```powershell
    drone-app/requirements.txt を作成して。pymavlinkライブラリを使用します。
    ```
2. ターミナルで下記コマンドを実行し、ライブラリをインストールする。
    ```powershell
    pip install -r drone-app/requirements.txt
    ```

## 実装・テスト
1. Mission Plannerを起動してシミュレーション環境を準備する。
   * Mission Planner起動後、上部メニューの `シミュレーション` ボタンをクリック
   * 次の画面で `Multirotor（マルチローター）` を選択
   * ダイアログの `Stable` ボタンをクリック
   * ArduPilotシミュレータが起動し、`tcp:127.0.0.1:5762`で待ち受けを開始
   * シミュレーション環境でMAVLink通信が可能になることを確認
2. Gemini CLIに下記プロンプトを入力して、実装を指示する。
    ```powershell
    @drone-app/REQUIREMENTS.md を参照して drone-app/main.py に実装を開始して。起動方法や使用方法は drone-app/README.mdに記載して。
    ```
    > 💡**TIPS**  
    > `@` はプロジェクト内ファイルの参照を表します。
3. AIは作業が完了したら、アプリ起動方法を回答するので内容を確認し実行する。下記は回答例。
    ```powershell
    1. Mission Plannerで上記手順でシミュレーションを開始します。
    2. python drone-app/main.py コマンドでドローン制御アプリを実行します。
    3. tcp:127.0.0.1:5762のポートで通信を確認します。
    ```
## デバッグ
1. エラーが発生した場合はプロンプトにエラーメッセージを入力して調査・修正を依頼する。下記はプロンプト例。
    ```powershell
    ドローンへの接続時に下記エラーが発生します。
    
    Connection refused: [Errno 10061] No connection could be made because the target machine actively refused it
    ```
    > 💡**TIPS**  
    > `Alt` + `Enter` でプロンプトの改行が可能です。
3. 期待通りの結果が得られない場合は状況をプロンプトに入力して、調査・修正を依頼する。下記はプロンプト例。
    ```powershell
    アームコマンドを送信してもドローンがアームしません。調査・修正をお願いします。
    ```
4. Mission Plannerの画面キャプチャなどの画像を渡したい場合はファイルパスを入力して調査・修正を依頼する。下記はプロンプト例。
    ```powershell
    Mission Plannerでエラーが表示されているので @drone-app\error_screenshot.png を見て修正してください。
    ```

# Web版ドローン制御アプリ開発（応用）

CUI版アプリの機能をWebブラウザから実行できるように拡張します。

## 要件定義
1. Gemini CLIに下記プロンプトを入力して、Web APIの要件定義書作成を指示する。
    ```powershell
    Web版ドローン制御アプリの要件定義書を drone-web-app/REQUIREMENTS.md として作成してください。CUI版の各機能をWeb APIとして呼び出せるようにします。バックエンドはPythonとFastAPI、フロントエンドはHTML/JavaScript/CSSで実装します。
    ```

## 依存ライブラリ定義
1. Gemini CLIに下記プロンプトを入力して、バックエンドに必要なライブラリを定義したファイルを作成する。
    ```powershell
    drone-web-app/backend/requirements.txt を作成して。pymavlink, fastapi, uvicornライブラリを使用します。
    ```
2. ターミナルで下記コマンドを実行し、ライブラリをインストールする。
    ```powershell
    pip install -r drone-web-app/backend/requirements.txt
    ```

## 実装
1. Gemini CLIに下記プロンプトを入力して、バックエンドとフロントエンドの実装を指示する。
    ```powershell
    @drone-web-app/REQUIREMENTS.md を参照してWebアプリを実装してください。バックエンドは drone-web-app/backend/main.py に、フロントエンドは drone-web-app/frontend/ にそれぞれ実装してください。
    ```
2. AIの作業が完了したら、`drone-web-app` ディレクトリにファイルが作成されていることを確認する。

## デバッグ
Webアプリ開発では、CORS (Cross-Origin Resource Sharing)エラーが頻繁に発生します。これは、Webページが異なるオリジン（ドメイン、プロトコル、ポート）のリソースにアクセスしようとするのをブラウザがブロックするために起こります。

1. フロントエンドからバックエンドAPIを呼び出した際に、ブラウザの開発者コンソールでCORSエラーが確認された場合、下記プロンプトで修正を依頼する。
    ```powershell
    FastAPIでCORSエラーが発生します。全てのオリジンからのアクセスを許可するように修正してください。
    ```

# まとめ・次の一手
* Vibeコーディングの基本的な流れ（要件定義 -> 実装 -> デバッグ）を体験できました。
* AIが生成したドキュメントやソースコードの理解が難しい場合はAIに解説を依頼することも有効です。
    * プロンプト例：`ソースコードの解説をお願いします。`, `MAVLinkプロトコルについて詳しく教えてください。`

* 下記のような機能拡張が考えられるので、ぜひチャレンジしてみてください。
    * 高度制御、速度制御機能の追加
    * ウェイポイント飛行機能の実装
    * リアルタイム位置情報表示のGUI作成
    * ドローンからの画像取得機能
    * フライトログの記録・分析機能

# 用語集

| 用語 | 説明 |
| --- | --- |
| ドローン (Drone) | 無人で遠隔操作や自動操縦で飛行する航空機。 |
| アーム (Arm) / ディスアーム (Disarm) | モーターの起動準備（アーム）と安全停止（ディスアーム）。 |
| 離陸 (Takeoff) | 地面から上昇し、指定高度に達すること。 |
| 着陸 (Land) | 現在位置に降下し、着地すること。同名のフライトモードもある。 |
| 位置情報 (Position/Location) | ドローンの地理的な位置（緯度・経度・高度）。 |
| 姿勢情報 (Attitude) | ドローンの傾き（ロール、ピッチ）と方角（ヨー）。 |
| フライトモード (Flight Mode) | ドローンの飛行制御方法を切り替えるモード。 |
| GUIDEDモード | 外部コンピュータからの指示に従って飛行するモード。 |
| AUTOモード | 設定されたミッションを自動実行するモード。 |
| RTL (Return to Launch)モード | 離陸地点へ自動帰還するモード。 |
| ウェイポイント (Waypoint) | 自動飛行で経由する地点（緯度・経度・高度）。 |
| ミッション (Mission) | ウェイポイント飛行など、ドローンが自動実行する一連の行動計画。 |
| 地上管制ソフト (GCS) | PC等でドローンを監視・制御するソフトウェア。 |
| コマンド (Command) | ドローンに特定の動作をさせるためのMAVLink命令。 |
| シミュレーション (SITL) | 実機を使わず、PC上でドローンの飛行を再現する技術。 |
| MAVLink (Micro Air Vehicle Link) | 小型無人機用の通信プロトコル。機体情報や制御コマンドをやり取りする。 |
| Pymavlink | MAVLinkプロトコルをPythonで扱うためのライブラリ。 |
| ArduPilot | オープンソースのドローン自動操縦（オートパイロット）ソフトウェア。 |
| Mission Planner | ArduPilot用の地上管制ソフト(GCS)。設定、監視、飛行計画に使用。 |