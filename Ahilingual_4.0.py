import discord
from discord import app_commands
import re
import deepl
import datetime
import os
import asyncio
from dotenv import load_dotenv

# 取得したトークンを環境変数(.envファイル)から取得
#！！！！！！！！！！！！！！！！！！！！！！！
#！！！！！！.envファイルは流出厳禁！！！！！！
#！！！！！！！！！！！！！！！！！！！！！！！
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
guild_ids_str = os.getenv("GUILDS_IDS", "")

MY_GUILDS = []
GUILD_NAMES = {}

for item in guild_ids_str.split(","):
    item = item.strip()
    if not item:
        continue
    
    # ":" があればIDと名前に分け,なければ名前を「名称未設定」にする
    if ":" in item:
        g_id_str, g_name = item.split(":", 1)
    else:
        g_id_str = item
        g_name = "名称未設定"
        
    try:
        g_id = int(g_id_str.strip())
        MY_GUILDS.append(discord.Object(id=g_id))  # コマンド登録用
        GUILD_NAMES[g_id] = g_name.strip()         # ログ表示用
    except ValueError:
        print(f"IDの読み込みエラー: {item}")


#MY_GUILDS = [discord.Object(id=int(g.strip())) for g in guild_ids_str.split(",") if g.strip()]



translator = deepl.Translator(DEEPL_API_KEY)


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# メッセージコマンドを登録するためのTreeを作成
tree = app_commands.CommandTree(client)

# 文章の中にひらがな・カタカナ・漢字が含まれているか判定
def contains_japanese(text):
    return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', text))

@client.event
async def on_ready():
    # ステータスをオンラインに設定，Type /help for guide を表示
    activity = discord.Activity(name = "/help for info", type=discord.ActivityType.listening)
    await client.change_presence(status=discord.Status.online, activity=activity)

# 過去のグローバルコマンドを空にして同期
    tree.clear_commands(guild=None)
    await tree.sync(guild=None)


    # MY_GUILDの中に入ってる，契約されているサーバーを一つずつ取り出して同期,表示
    for guild in MY_GUILDS:
        server_name = GUILD_NAMES.get(guild.id, "不明なサーバー")
        try:
            await tree.sync(guild=guild)
            print(f"サーバID {guild.id} 同期完了 [{server_name}]")
        except Exception as e:
            print(f"サーバID {guild.id} 同期失敗: {e} [{server_name}]")

    print(f"{client.user} 準備完了")


#----------------------------------------------------------------------------------------------------------------------
#       1. コマンドから個人だけに翻訳を表示するプログラム
#----------------------------------------------------------------------------------------------------------------------

# アプリ起動時にコマンドをDiscordへ登録（同期）する

# --- 右クリック（長押し）から呼び出すメニュー ---
@tree.context_menu(name="Translate / 翻訳する", guilds = MY_GUILDS)
async def translate_message(interaction: discord.Interaction, message: discord.Message):
    #ログを記録
    #print(f"[LOG]{interaction.user}")
    if not message.content:
        await interaction.response.send_message("Quack!!", ephemeral=True)
        return

    # インタラクションの応答期限(3s)切れを防ぐため、先に「考え中」状態にする
    await interaction.response.defer(ephemeral=True)

    try:
        #元のメッセージへ戻るリンクを表示
        jump_link = message.jump_url
        if contains_japanese(message.content):
            result = translator.translate_text(message.content, target_lang="EN-US")
            reply_text = f"**{message.author.display_name}**\n{result.text}\n-# [Back to original]({jump_link})\n"
        else:
            result = translator.translate_text(message.content, target_lang="JA")
            reply_text = f"**{message.author.display_name}**\n{result.text}\n-# [元の文に戻る]({jump_link})\n"
            
        # 結果をエフェメラルで送信
        await interaction.followup.send(reply_text, ephemeral=True)

    except Exception as e:
        print(f"Translation Error: {e}")
        await interaction.followup.send("...??", ephemeral=True)


# ---------------------------------------------------------------------------------------------------------------------
#       2.メンションされたときに返すプログラム
#----------------------------------------------------------------------------------------------------------------------
@client.event
async def on_message(message):
    #ログを表示する
    #now = datetime.datetime.now().strftime("%m/%d %H:%M:%S")
    #print(f"{now}  [{message.author}]:{message.content}")
    
    if message.author == client.user:
        return

    #許可されたサーバー以外では反応しない
    if message.guild is None or message.guild.id not in [guild.id for guild in MY_GUILDS]:
        return

    
    # メンションされた時だけ反応
    if client.user in message.mentions:
        mention_pattern = rf'<@!?{client.user.id}>'
        user_input = re.sub(mention_pattern, '', message.content).strip()
        
        # メンションだけでテキストが無い場合の処理
        if not user_input:
            await message.reply("Quack!!")
            return

        async with message.channel.typing():
            try:
                if contains_japanese(user_input):
                    # 日本語が含まれていれば英語へ翻訳
                    result = translator.translate_text(user_input, target_lang="EN-US")
                    reply_text = f"{result.text}\n-# (Translated)"
                else:
                    # 日本語が含まれていなければ日本語へ翻訳
                    result = translator.translate_text(user_input, target_lang="JA")
                    reply_text = f"{result.text}\n-# (翻訳されました)"
                    
                await message.reply(reply_text, mention_author=False)
                
            except Exception as e:
                print(f"Translation Error: {e}")
                await message.reply(f"...??\n[Translation Error: {e}]")

#--------------------------------------------------------------------------------------------------------------------------
#       3.ヘルプコマンド
#--------------------------------------------------------------------------------------------------------------------------
@tree.command(name="help", description="Show how to use Ahilingual", guilds=MY_GUILDS)
async def help_command(interaction: discord.Interaction):

    #file = discord.File("Ahilingual.png", filename="logo.png")

    # 2. 日本語のEmbedを作成（元のコードそのまま）
    embed_ja = discord.Embed(
        title="**【アヒリンガルの使い方🦆】**",
        description="Discordのメッセージを自動翻訳するbotです。2種類の翻訳機能があります。",
        color=0xffd700
    )
    #embed_ja.set_image(url="attachment://logo.png")
    embed_ja.add_field(
        name="**①文章中でメンションして翻訳**",
        value="送る文章中で<@1543876201993740341>をメンションすると、その文章の翻訳を返信してくれます。\n\n",
        inline=False
    )
    embed_ja.add_field(
        name="**②静かに翻訳**",
        value="自分だけに翻訳結果を表示する機能を追加しました。\n1. 翻訳したいメッセージを長押し(PCの場合は右クリック)で表示されるメニューから「アプリ」を選択\n2.「Ahilingual」を選択\n3.「Translate / 翻訳する」を選択\n重要なチャットを流すことなく翻訳を見ることができます。\n ",
        inline=False
    )
    #embed_ja.add_field(
    #    name="**追記**",
    #    value="翻訳にはDeepL公式APIを使用しています。月10万文字までタダで翻訳できるらしい。太っ腹ですね。\nプログラムは研究室のサーバでぶん回したまま放置してるのでたまに止まってるかもです。\nエラーの報告やフィードバックは<@826416973978140712>までお願いします。\n ",
    #    inline=False
    #)

    # 3. 英語のEmbedを作成（元のコードそのまま）
    embed_en = discord.Embed(
        title="**【How to Use Ahilingual】**",
        description="Ahilingual is a bot that automatically translates messages on Discord. It has 2 main features.",
        color=0xffd700
    )
    #embed_en.set_image(url="attachment://logo.png")
    embed_en.add_field(
        name="**①Mention Ahilingual in a message**",
        value="\nJust mention <@1543876201993740341> in your message, and the bot will reply with the translation.\n ",
        inline=False
    )
    embed_en.add_field(
        name="**②Silent translation**",
        value="This feature displays the translation results only to you.\n1. Long-press the message you want to translate (right-click on a PC), then select “Apps” from the menu that appears\n2. Select “Ahilingual”\n3. Select “Translate / 翻訳する”\nYou can view the translation without letting important chat messages scroll away.",
        inline=False
    )
    #embed_en.add_field(
    #    name="**Other Notes**",
    #    value="This program uses DeepL API for translations. Please send error reports and feedback to <@826416973978140712>",
    #    inline=False
    #)
    
    # 4. エフェメラルで送信
    await interaction.response.send_message(embeds=[embed_ja, embed_en], ephemeral=True)

#keep_yourself_alive()
client.run(DISCORD_TOKEN)
