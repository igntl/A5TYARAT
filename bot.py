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

# رومات الكباتن بالترتيب الدقيق من 1 إلى 8
TEAM_CHANNELS = [
    1483219750027919422,  # روم الكابتن الأول
    1513180587584782446,  # روم الكابتن الثاني
    1514791919623077938,  # روم الكابتن الثالث
    1514791956763512874,  # روم الكابتن الرابع
    1523555136050303017,  # روم الكابتن الخامس
    1523555190102556703,  # روم الكابتن السادس
    1523555255751545032,  # روم الكابتن السابع
    1523555313515761744   # روم الكابتن الثامن
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
        print(" تم تشغيل البوت بنظام تخصيص اللفات لكل كابتن!")

bot = NewProClubBot()

# ذاكرة حفظ البيانات الحالية
session = {
    "active": False,
    "captains": [],
    "round": 1,
    "current_index": 0,
    "custom_picks_r1": {},  # حصص اللفة الأولى {كابتن_آيدي: عدد_الاختيارات}
    "custom_picks_r2": {}   # حصص اللفة الثانية {كابتن_آيدي: عدد_الاختيارات}
}

# تابع بناء خيارات القائمة المنسدلة بناءً على المتواجدين بالروم الصوتي حالياً فقط
def make_options(guild, page=0):
    lobby_channel = guild.get_channel(LOBBY_VOICE_ID)
    if not lobby_channel:
        return [], []
        
    valid_members = [m for m in lobby_channel.members if m.id not in session["captains"] and not m.bot]
            
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
    def __init__(self, guild, max_picks=2, page=0):
        self.guild = guild
        self.page = page
        self.max_picks = max_picks
        
        options, _ = make_options(guild, page)
        
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
            await interaction.response.send_message("❌ ليس دورك في الاختيار الآن انتظر منشن البوت.", ephemeral=True)
            return

        selection = self.values[0]
        
        if selection.startswith("page_next_"):
            p = int(selection.split("_")[2])
            await interaction.response.edit_message(view=DraftView(interaction.guild, self.max_picks, p + 1))
            return
        elif selection.startswith("page_prev_"):
            p = int(selection.split("_")[2])
            await interaction.response.edit_message(view=DraftView(interaction.guild, self.max_picks, p - 1))
            return
        elif selection == "none":
            await interaction.response.edit_message(view=DraftView(interaction.guild, self.max_picks, self.page))
            return

        selected_members = [int(v) for v in self.values if not v.startswith("page_")]
        lobby_channel = interaction.guild.get_channel(LOBBY_VOICE_ID)
        current_lobby_ids = [m.id for m in lobby_channel.members] if lobby_channel else []

        missing_players = [p_id for p_id in selected_members if p_id not in current_lobby_ids]
        if missing_players:
            await interaction.response.edit_message(
                content=f"{interaction.user.mention} ⚠️ خرج بعض اللاعبين أو تغيرت روماتهم! تم تحديث القائمة تلقائياً بالمتواجدين حالياً، يرجى إعادة الاختيار.",
                view=DraftView(interaction.guild, self.max_picks, self.page)
            )
            return

        await interaction.response.defer()
        
        target_room_id = TEAM_CHANNELS[session["current_index"]]
        target_room = interaction.guild.get_channel(target_room_id)
        
        for p_id in selected_members:
            member = interaction.guild.get_member(p_id)
            if member and member.voice and member.voice.channel:
                try:
                    await member.move_to(target_room)
                except:
                    pass

        # الانتقال للكابتن التالي
        session["current_index"] += 1
        if session["current_index"] >= len(session["captains"]):
            session["current_index"] = 0
            session["round"] += 1  # الانتقال للفة القادمة

        try:
            await interaction.message.delete()
        except:
            pass
            
        await send_next_turn(interaction.channel, interaction.guild)

class DraftView(discord.ui.View):
    def __init__(self, guild, max_picks=2, page=0):
        super().__init__(timeout=None)
        self.add_item(DraftMenu(guild, max_picks, page))

class ResetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=" إنهاء التقسيمه وإعادة تهيئة البوت", style=discord.ButtonStyle.danger)
    async def callback(self, interaction: discord.Interaction):
        if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
            await interaction.response.send_message("❌ هذا الخيار مخصص للمسؤولين فقط.", ephemeral=True)
            return
        session["active"] = False
        session["captains"] = []
        session["round"] = 1
        session["current_index"] = 0
        session["custom_picks_r1"] = {}
        session["custom_picks_r2"] = {}
        await interaction.response.edit_message(content=" **تم إنهاء التقسيمه وتصفير البوت بنجاح جاهز للتقسيمة القادمة.**", embed=None, view=None)

class ResetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ResetButton())

# دالة تحديد الحصة بناءً على مدخلات المسؤول لكل كابتن منفصل
def get_current_max_picks(captain_id):
    if session["round"] == 1:
        return session["custom_picks_r1"].get(captain_id, 2)
    elif session["round"] == 2:
        return session["custom_picks_r2"].get(captain_id, 2)
    else:
        return 2  # تلقائياً من اللفة الثالثة وطالع يصبح الاختيار 2 دائماً لجميع الكباتن

async def send_next_turn(channel, guild):
    options, actual_available = make_options(guild)
    
    if not actual_available:
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

    picks_allowed = get_current_max_picks(cap_id)
    
    embed = discord.Embed(
        title=f"📋 جولة الاختيار رقم {session['round']}",
        description=f"الدور الآن عندك يا كابتن: {captain_member.mention}\n"
                    f"الرجاء اختيار لاعبيك المفضلين من القائمة بالأسفل.\n\n"
                    f" اختياراتك المتاحة في هذا الدور: **{picks_allowed} لاعبين** دفعة واحدة.",
        color=discord.Color.blue()
    )
    await channel.send(content=captain_member.mention, embed=embed, view=DraftView(guild, picks_allowed))

# --- تم إعادة ترتيب المتواجدات لتجنب الـ SyntaxError تماماً وفقاً لقواعد بايثون ---
@bot.tree.command(name="تقسيم", description="بدء التقسيم مع تحديد اختيارات اللفة 1 و 2 لكل كابتن بشكل مستقل")
@app_commands.describe(
    عدد_الفرق="اختر عدد الفرق المشاركة (2، 4، 6، أو 8)",
    كابتن_1="الكابتن 1", كابتن_2="الكابتن 2", كابتن_3="الكابتن 3 (اختياري)", كابتن_4="الكابتن 4 (اختياري)",
    كابتن_5="الكابتن 5 (اختياري)", كابتن_6="الكابتن 6 (اختياري)", كابتن_7="الكابتن 7 (اختياري)", كابتن_8="الكابتن 8 (اختياري)",
    لفة1_كابتن1="حصة اللفة 1 لكابتن 1", لفة2_كابتن1="حصة اللفة 2 لكابتن 1",
    لفة1_كابتن2="حصة اللفة 1 لكابتن 2", لفة2_كابتن2="حصة اللفة 2 لكابتن 2",
    لفة1_كابتن3="حصة اللفة 1 لكابتن 3", لفة2_كابتن3="حصة اللفة 2 لكابتن 3",
    لفة1_كابتن4="حصة اللفة 1 لكابتن 4", لفة2_كابتن4="حصة اللفة 2 لكابتن 4",
    لفة1_كابتن5="حصة اللفة 1 لكابتن 5", لفة2_كابتن5="حصة اللفة 2 لكابتن 5",
    لفة1_كابتن6="حصة اللفة 1 لكابتن 6", لفة2_كابتن6="حصة اللفة 2 لكابتن 6",
    لفة1_كابتن7="حصة اللفة 1 لكابتن 7", لفة2_كابتن7="حصة اللفة 2 لكابتن 7",
    لفة1_كابتن8="حصة اللفة 1 لكابتن 8", لفة2_كابتن8="حصة اللفة 2 لكابتن 8"
)
async def تقسيم(
    interaction: discord.Interaction, عدد_الفرق: int, 
    كابتن_1: discord.Member, 
    كابتن_2: discord.Member, 
    كابتن_3: discord.Member = None, 
    كابتن_4: discord.Member = None, 
    كابتن_5: discord.Member = None, 
    كابتن_6: discord.Member = None, 
    كابتن_7: discord.Member = None, 
    كابتن_8: discord.Member = None, 
    لفة1_كابتن1: int = 2, لفة2_كابتن1: int = 2,
    لفة1_كابتن2: int = 2, لفة2_كابتن2: int = 2,
    لفة1_كابتن3: int = 2, لفة2_كابتن3: int = 2,
    لفة1_كابتن4: int = 2, لفة2_كابتن4: int = 2,
    لفة1_كابتن5: int = 2, لفة2_كابتن5: int = 2,
    لفة1_كابتن6: int = 2, لفة2_كابتن6: int = 2,
    لفة1_كابتن7: int = 2, لفة2_كابتن7: int = 2,
    لفة1_كابتن8: int = 2, لفة2_كابتن8: int = 2
):
    if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
        await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص فقط لمن يحمل رتبة المسؤول عن التقسيمة!", ephemeral=True)
        return

    if interaction.channel_id != TEXT_CHANNEL_ID:
        await interaction.response.send_message(f"❌ هذا الأمر يعمل فقط داخل شات البوت المخصص: <#{TEXT_CHANNEL_ID}>", ephemeral=True)
        return

    if عدد_الفرق not in [2, 4, 6, 8]:
        await interaction.response.send_message("❌ الرجاء اختيار عدد فرق صحيح (2 أو 4 أو 6 أو 8 فقط).", ephemeral=True)
        return

    lobby_channel = interaction.guild.get_channel(LOBBY_VOICE_ID)
    if not lobby_channel or not lobby_channel.members:
        await interaction.response.send_message("❌ روم التقسيمة الصوتي فارغ حالياً! يجب دخول اللاعبين أولاً.", ephemeral=True)
        return

    all_caps = [كابتن_1, كابتن_2, كابتن_3, كابتن_4, كابتن_5, كابتن_6, كابتن_7, كابتن_8]
    chosen_caps = [c.id for c in all_caps[:عدد_الفرق] if c is not None]

    if len(chosen_caps) != عدد_الفرق:
        await interaction.response.send_message(f"❌ خطأ: اخترت {عدد_الفرق} فرق ولكن لم تقم بمنشنة كباتن كافيين بالتوالي.", ephemeral=True)
        return

    # حفظ الحصص الفردية المحددة في الذاكرة
    r1_inputs = [لفة1_كابتن1, لفة1_كابتن2, لفة1_كابتن3, لفة1_كابتن4, لفة1_كابتن5, لفة1_كابتن6, لفة1_كابتن7, لفة1_كابتن8]
    r2_inputs = [لفة2_كابتن1, لفة2_كابتن2, لفة2_كابتن3, لفة2_كابتن4, لفة2_كابتن5, لفة2_كابتن6, لفة2_كابتن7, لفة2_كابتن8]
    
    r1_map = {}
    r2_map = {}
    for i in range(عدد_الفرق):
        c_id = all_caps[i].id
        r1_map[c_id] = r1_inputs[i] if r1_inputs[i] > 0 else 2
        r2_map[c_id] = r2_inputs[i] if r2_inputs[i] > 2 else 2

    session["active"] = True
    session["captains"] = chosen_caps
    session["current_index"] = 0
    session["round"] = 1
    session["custom_picks_r1"] = r1_map
    session["custom_picks_r2"] = r2_map

    await interaction.response.send_message(f" **بدأت التقسيمة لـ {عدد_الفرق} فرق بحصص مخصصة لأول لفتين وتلقائياً 2 لاعبين من اللفة الثالثة!**")
    await send_next_turn(interaction.channel, interaction.guild)

# --- أمر التحديث الإجباري العادي بالشات لتهيئة الرومات والأمر الجديد ---
@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("🔄 تم تحديث ومزامنة نظام التقسيم بحصص اللفات المستقلة بنجاح!")

# تشغيل البوت
token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("Error: DISCORD_TOKEN is missing.")
