# QuotaPet

**An unofficial Linux companion that shows the remaining 7-day Codex usage limit around the desktop pet.**

QuotaPet draws a transparent, click-through ring around the Codex pet. The ring follows the pet, hides when the pet is closed, and uses cyan, amber, and red as the remaining allowance gets lower. It is a separate desktop process; it does not modify Codex or the pet artwork.

> **Experimental:** Usage data comes from a private, undocumented ChatGPT endpoint. The endpoint, response format, and availability may change. OpenAI has not endorsed this project. Review the data and policy notes below before installing.

## Features

- Shows the remaining capacity in the 7-day usage window.
- Refreshes usage about once a minute.
- Follows the pet's saved position and window group.
- Passes mouse input through to the pet so it remains draggable.
- Hides when the pet is closed.
- Runs as a per-user `systemd` service and does not require root access.

## Requirements

- Linux with an X11 display, or an XWayland session. Native Wayland is not supported.
- Codex Desktop with a pet enabled and a signed-in ChatGPT account.
- Python 3, GTK 3 with PyGObject, Pycairo, `python-xlib`, and a `systemd --user` session.

On Debian or Ubuntu, the Python and GTK dependencies are available from the distribution packages:

```bash
sudo apt install python3 python3-gi gir1.2-gtk-3.0 python3-cairo python3-xlib
```

## Install

```bash
git clone https://github.com/HidemitsuNishioka/CodexPetQuotaRing.git
cd CodexPetQuotaRing
bash ./install.sh
```

The installer copies the app to `~/.local/share/codex-weekly-ring/`, creates a launcher in `~/.local/bin/`, and enables and starts the `codex-weekly-ring.service` user service for the graphical session.

Check the service and application log:

```bash
systemctl --user status codex-weekly-ring.service
tail -f ~/.local/state/codex-weekly-ring/app.log
```

Remove the app and its user service:

```bash
bash ./uninstall.sh
```

## Data and privacy

QuotaPet reads these local Codex files:

| File | Purpose |
| --- | --- |
| `~/.codex/.codex-global-state.json` | Checks whether the pet is open and reads its saved position. |
| `~/.codex/auth.json` | Reads the existing local access token for the live usage request. |
| `~/.codex/logs_2.sqlite` | Reads the latest cached `codex.rate_limits` event if the live request is unavailable. |

For live usage, QuotaPet sends an HTTPS `GET` request about once a minute to `https://chatgpt.com/backend-api/wham/usage`, using the access token in an `Authorization` header. The request goes to `chatgpt.com`; QuotaPet has no telemetry service or project server. The token and response body are not written to the app log or saved by QuotaPet. The cached fallback is read-only.

The live endpoint is not documented as a public API. This project has not received confirmation that automated access to it is supported. OpenAI's [Terms of Use](https://openai.com/policies/terms-of-use/) include restrictions on automated or programmatic data extraction. The applicability of those terms to this usage indicator has not been determined. Check the current terms and use the app at your discretion. The displayed usage can be missing or stale if the endpoint or local Codex data format changes.

## Scope and attribution

This is an unofficial Linux implementation inspired by the companion-overlay idea in [petergpt/codex-pet-limit-rings](https://github.com/petergpt/codex-pet-limit-rings). That project is a separate macOS app. This repository is not affiliated with or endorsed by OpenAI or the upstream project's maintainer. OpenAI names are used only to describe compatibility; no OpenAI logos are included.

## License

No license has been selected for this repository yet. The MIT license in the upstream repository applies to that repository's code; it does not automatically license this project. Add a license before making this repository public or granting permission to redistribute its code.

---

## 日本語

QuotaPet は、Codex デスクトップのペットの周囲に、**7日間の利用枠の残量**を円形で表示する非公式 Linux 用アプリです。クリック透過のリングがペットの位置に追従し、ペットを閉じるとリングも隠れます。Codex 本体やペットの画像は変更しません。

> **実験的な実装です。** 利用量の取得には、非公開で仕様が公開されていない ChatGPT のエンドポイントを使います。接続先や応答形式が変更・停止される可能性があります。OpenAI の公式アプリではありません。インストール前に、以下のデータと規約に関する説明を確認してください。

### 必要な環境

- Linux の X11、または XWayland セッション（ネイティブ Wayland には非対応）
- ペットを有効にした Codex Desktop と、サインイン済みの ChatGPT アカウント
- Python 3、GTK 3 / PyGObject、Pycairo、`python-xlib`、`systemd --user`

Debian / Ubuntu では、依存パッケージを次のようにインストールできます。

```bash
sudo apt install python3 python3-gi gir1.2-gtk-3.0 python3-cairo python3-xlib
```

### インストール

```bash
git clone https://github.com/HidemitsuNishioka/CodexPetQuotaRing.git
cd CodexPetQuotaRing
bash ./install.sh
```

アプリを `~/.local/share/codex-weekly-ring/` にコピーし、ユーザー用ランチャーとグラフィカルセッション向けの `systemd` サービスを登録して起動します。root 権限は不要です。

```bash
systemctl --user status codex-weekly-ring.service
tail -f ~/.local/state/codex-weekly-ring/app.log
bash ./uninstall.sh
```

### データとプライバシー

- `~/.codex/.codex-global-state.json` からペットの表示状態と保存位置を読みます。
- `~/.codex/auth.json` にある既存のアクセストークンを読み、約1分ごとに `chatgpt.com` へ利用量を問い合わせます。
- 通信できない場合は `~/.codex/logs_2.sqlite` の最新 `codex.rate_limits` イベントを読み取り、表示に使います。
- リクエストは HTTPS で `https://chatgpt.com/backend-api/wham/usage` に送信します。トークンや応答本文をアプリのログへ記録したり、QuotaPet が保存したりはしません。テレメトリ用の外部サーバーはありません。

このエンドポイントは公開 API として仕様が公開されておらず、自動アクセスがサポートされるとの確認も得ていません。OpenAI の[利用規約](https://openai.com/policies/terms-of-use/)には、データの自動・プログラムによる取得に関する制限があります。この利用量表示への適用関係は確認できていません。利用前に最新の規約を確認してください。接続先や Codex のローカルデータ形式が変わると、利用量が表示されない、または古い値になることがあります。

### 参考元とライセンス

ペットに別ウィンドウを重ねるアイデアは [petergpt/codex-pet-limit-rings](https://github.com/petergpt/codex-pet-limit-rings) を参考にしています。同リポジトリは別個の macOS アプリです。このプロジェクトは OpenAI および元リポジトリの開発者とは無関係で、公式の承認を受けていません。

このリポジトリのライセンスはまだ選定されていません。元リポジトリの MIT ライセンスは元リポジトリのコードに適用されるもので、このプロジェクトに自動的に適用されるものではありません。公開や再配布を許可する前に、ライセンスを追加してください。
