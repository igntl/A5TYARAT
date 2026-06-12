import discord
from discord.ext import commands
from discord import app_commands
import os

# --- إعدادات الآيديات الثابتة الحصرية بسيرفرك ---
ROLE_MANAGER_ID = 1475334752436359320       # رتبة المسؤول عن التقسيمة
ROLE_HEZAM_ID = 1490247564086214787         # رتبة الحزام
ROLE_CAPITANO_ID = 1495426762971283528      # رتبة كابيتانو

TEXT_CHANNEL_ID = 1483219896069525665       # شات البوت الكتابي المسموح به
LOBBY_VOICE_ID = 1475334190034587661        # روم التقسيمة الصوتي (التجمع)

# رومات الكباتن بالترتيب الدقيق من 1 إلى 6
TEAM_CHANNELS = [
    1483219750027919422,  # روم الكابتن الأول
    1513180587584782446,  # روم الكابتن الثاني
    0,                    # روم الكابتن 3 (استبدل الـ 0 بالآيدي عند الحاجة)
    0,                    # روم الكابتن 4 (استبدل الـ 0 بالآيدي عند الحاجة)
    0,                    # روم الكابتن 5 (استبدل الـ 0 بالآيدي عند الحاجة)
    0                     # روم الكابتن 6 (استبدل الـ 0 بالآيدي عند الحاجة)
]

# --- إعدادات البوت الأساسية ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

class NewProClubBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        await self.tree.sync()
        print("⚽ تم تشغيل البوت بنجاح ومزامنة الأوامر!")

bot = NewProClubBot()

# ذاكرة حفظ البيانات الحالية
session = {
    "active": False,
    "captains": [],
    "players": [],
    "current_index": 0,
    "round": 1
}

# تابع بناء خيارات القائمة المنسدلة
def make_options(player_ids, guild, page=0):
    valid_members = []
    for p_id in player_ids:
        m = guild.get_member(p_id)
        if m and m.voice and m.voice.channel and m.voice.channel.id == LOBBY_VOICE_ID:
            valid_members.append(m)
            
    start = page * 23
    end = start + 23
    current_list = valid_members[start:end]
    
    options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in current_list]
    
    if page > 0:
        options.insert(0, discord.SelectOption(label="⬅️ الصفحة السابقة", value=f"page_prev_{page}"))
    if end < len(valid_members):
        options.append(discord.SelectOption(label="➡️ الصفحة التالية", value=f"page_next_{page}"))
        
    if not options:
        options.append(discord.SelectOption(label="لا يوجد لاعبين متاحين حالياً بروم التجمع", value="none"))
    return options, valid_members

# الواجهة البرمجية المباشرة لاختيار اللاعبين
class DraftMenu(discord.ui.Select):
    def __init__(self, player_ids, guild, max_picks=2, page=0):
        options, _ = make_options(player_ids, guild, page)
        self.page = page
        self.player_ids = player_ids
        self.max_picks = max_picks
        super().__init__(
            placeholder="اختار من القائمة اللي تحت...",
            min_values=1,
            max_values=min(max_picks, len(options)),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if not session["active"]:
            await interaction.response.send_message("❌ لا توجد تقسيمة نشطة حالياً.", ephemeral=True)
            return
            
        current_cap_id = session["captains"][session["current_index"]]
        if interaction.user.id != current_cap_id:
            await interaction.response.send_message("❌ ليس دورك في الاختيار الآن! انتظر منشن البوت.", ephemeral=True)
            return

        selection = self.values[0]
        
        # التعامل مع أزرار التنقل بين الصفحات
        if selection.startswith("page_next_"):
            p = int(selection.split("_")[2])
            await interaction.response.edit_message(view=DraftView(self.player_ids, interaction.guild, self.max_picks, p + 1))
            return
        elif selection.startswith("page_prev_"):
            p = int(selection.split("_")[2])
            await interaction.response.edit_message(view=DraftView(self.player_ids, interaction.guild, self.max_picks, p - 1))
            return
        elif selection == "none":
            return

        await interaction.response.defer()
        
        # تجهيز ونقل اللاعبين المختارين فورا
        selected_members = [int(v) for v in self.values if not v.startswith("page_")]
        target_room_id = TEAM_CHANNELS[session["current_index"]]
        target_room = interaction.guild.get_channel(target_room_id)
        
        for p_id in selected_members:
            if p_id in session["players"]:
                session["players"].remove(p_id)
                member = interaction.guild.get_member(p_id)
                if member and member.voice and member.voice.channel:
                    try:
                        await member.move_to(target_room)
                    except:
                        pass

        # الانتقال للكابتن التالي مباشرة
        session["current_index"] += 1
        if session["current_index"] >= len(session["captains"]):
            session["current_index"] = 0
            session["round"] += 1

        try:
            await interaction.message.delete()
        except:
            pass
            
        await send_next_turn(interaction.channel, interaction.guild)

class DraftView(discord.ui.View):
    def __init__(self, player_ids, guild, max_picks=2, page=0):
        super().__init__(timeout=None)
        self.add_item(DraftMenu(player_ids, guild, max_picks, page))

# واجهة إعادة التهيئة النهائية
class ResetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🏁 إنهاء السهرة وإعادة تهيئة البوت", style=discord.ButtonStyle.danger)
    async def callback(self, interaction: discord.Interaction):
        if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
            await interaction.response.send_message("❌ هذا الخيار مخصص للمسؤولين فقط.", ephemeral=True)
            return
        session["active"] = False
        session["players"] = []
        session["captains"] = []
        await interaction.response.edit_message(content="🏁 **تم إنهاء التقسيمه وتصفير البوت بنجاح! جاهز للتقسيمة القادمة.**", embed=None, view=None)

class ResetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ResetButton())

# دالة إرسال جولة الاختيار التالية
async def send_next_turn(channel, guild):
    _, actual_available = make_options(session["players"], guild)
    session["players"] = [m.id for m in actual_available]
    
    if not session["players"]:
        embed = discord.Embed(
            title=" تم توزيع جميع اللاعبين بنجاح !",
            description="انتهت عملية التقسيمه بالكامل، يتوجب على المسؤول الضغط على الزر بالأسفل لتصفير البوت.",
            color=discord.Color.green()
        )
        await channel.send(embed=embed, view=ResetView())
        return

    cap_id = session["captains"][session["current_index"]]
    captain_member = guild.get_member(cap_id)
    
    if not captain_member:
        session["current_index"] += 1
        if session["current_index"] >= len(session["captains"]):
            session["current_index"] = 0
            session["round"] += 1
        await send_next_turn(channel, guild)
        return

    # تم التثبيت على لاعبين اثنين (2) في كل دور لجميع الكباتن دائماً
    picks_allowed = 2
    
    embed = discord.Embed(
        title=f"📋 جولة الاختيار رقم {session['round']}",
        description=f"الدور الآن عندك يا كابتن: {captain_member.mention}\n"
                    f"الرجاء اختيار لاعبيك المفضلين من القائمة بالأسفل.\n\n"
                    f"⚡ حصتك المتاحة في هذا الدور: **{picks_allowed} لاعبين** دفعة واحدة.",
        color=discord.Color.blue()
    )
    await channel.send(content=captain_member.mention, embed=embed, view=DraftView(session["players"], guild, picks_allowed))

# --- الأمر المائل الأساسي المطور المباشر ---
@bot.tree.command(name="تقسيم", description="بدء نظام التقسيمات المباشر ")
@app_commands.describe(
    عدد_الفرق="اختر عدد الفرق المشاركة (2 أو 4 أو 6)",
    كابتن_1="الكابتن الأول لروم 1",
    كابتن_2="الكابتن الثاني لروم 2",
    كابتن_3="الكابتن الثالث لروم 3 (اختياري)",
    كابتن_4="الكابتن الرابع لروم 4 (اختياري)",
    كابتن_5="الكابتن الخامس لروم 5 (اختياري)",
    كابتن_6="الكابتن السادس لروم 6 (اختياري)"
)
async def تقسيم(
    interaction: discord.Interaction, 
    عدد_الفرق: int, 
    كابتن_1: discord.Member, 
    كابتن_2: discord.Member,
    كابتن_3: discord.Member = None,
    كابتن_4: discord.Member = None,
    كابتن_5: discord.Member = None,
    كابتن_6: discord.Member = None
):
    if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
        await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص فقط لمن يحمل رتبة المسؤول عن التقسيمة!", ephemeral=True)
        return

    if interaction.channel_id != TEXT_CHANNEL_ID:
        await interaction.response.send_message(f"❌ هذا الأمر يعمل فقط داخل شات البوت المخصص: <#{TEXT_CHANNEL_ID}>", ephemeral=True)
        return

    if عدد_الفرق not in [2, 4, 6]:
        await interaction.response.send_message("❌ الرجاء اختيار عدد فرق صحيح (2 أو 4 أو 6 فقط).", ephemeral=True)
        return

    lobby_channel = interaction.guild.get_channel(LOBBY_VOICE_ID)
    if not lobby_channel or not lobby_channel.members:
        await interaction.response.send_message("❌ روم التقسيمة الصوتي فارغ حالياً! يجب دخول اللاعبين أولاً.", ephemeral=True)
        return

    all_caps = [كابتن_1, كابتن_2, كابتن_3, كابتن_4, كابتن_5, كابتن_6]
    chosen_caps = [c.id for c in all_caps[:عدد_الفرق] if c is not None]

    if len(chosen_caps) != عدد_الفرق:
        await interaction.response.send_message(f"❌ خطأ: اخترت {عدد_الفرق} فرق ولكن لم تقم بمنشنة كباتن كافيين بالتوالي.", ephemeral=True)
        return

    pool = [m.id for m in lobby_channel.members if m.id not in chosen_caps]

    if not pool:
        await interaction.response.send_message("❌ لا يوجد لاعبين متاحين للتقسيم داخل الروم الصوتي (فقط الكباتن متواجدين)!", ephemeral=True)
        return

    session["active"] = True
    session["captains"] = chosen_caps
    session["players"] = pool
    session["current_index"] = 0
    session["round"] = 1

    await interaction.response.send_message(f"🎬 **بدأ نظام التقسيم التلقائي بنجاح لـ {عدد_الفرق} فرق!**")
    
    await send_next_turn(interaction.channel, interaction.guild)

# تشغيل البوت
token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("Error: DISCORD_TOKEN is missing.")
