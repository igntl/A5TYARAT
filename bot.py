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
    1514791919623077938,  # روم الكابتن 3
    1514791956763512874,  # روم الكابتن 4
    0,                    # روم الكابتن 5
    0                     # روم الكابتن 6
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
    "current_index": 0,
    "round": 1,
    "picks_allowed": 2  # القيمة الافتراضية التلقائية عند التشغيل
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
        
        # بناء الخيارات المبدئية عند إرسال القائمة أول مرة
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
            await interaction.response.send_message("❌ ليس دورك في الاختيار الآن! انتظر منشن البوت.", ephemeral=True)
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
            # تحديث ذكي تلقائي وإعادة عرض اللائحة إذا فتح القائمة وهي فارغة وضغط عليها
            await interaction.response.edit_message(view=DraftView(interaction.guild, self.max_picks, self.page))
            return

        # ميزة التحديث والتأكد اللحظي التلقائي قبل النقل (لمنع كراش السحب الخاطئ للأسماء المفقودة)
        selected_members = [int(v) for v in self.values if not v.startswith("page_")]
        lobby_channel = interaction.guild.get_channel(LOBBY_VOICE_ID)
        current_lobby_ids = [m.id for m in lobby_channel.members] if lobby_channel else []

        # التحقق: إذا حاول الكابتن اختيار شخص طلع من الروم فجأة، نحدث القائمة فوراً وننبهه
        missing_players = [p_id for p_id in selected_members if p_id not in current_lobby_ids]
        if missing_players:
            await interaction.response.edit_message(
                content=f"{interaction.user.mention} ⚠️ تملّص بعض اللاعبين أو تغيرت روماتهم! تم تحديث القائمة تلقائياً بالمتواجدين حالياً، يرجى إعادة الاختيار.",
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
    def __init__(self, guild, max_picks=2, page=0):
        super().__init__(timeout=None)
        self.add_item(DraftMenu(guild, max_picks, page))

class ResetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🏁 إنهاء السهرة وإعادة تهيئة البوت", style=discord.ButtonStyle.danger)
    async def callback(self, interaction: discord.Interaction):
        if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
            await interaction.response.send_message("❌ هذا الخيار مخصص للمسؤولين فقط.", ephemeral=True)
            return
        session["active"] = False
        session["captains"] = []
        session["picks_allowed"] = 2
        await interaction.response.edit_message(content="🏁 **تم إنهاء التقسيمه وتصفير البوت بنجاح! جاهز للتقسيمة القادمة.**", embed=None, view=None)

class ResetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ResetButton())

def get_current_max_picks():
    return session["picks_allowed"]

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

    picks_allowed = get_current_max_picks()
    
    embed = discord.Embed(
        title=f"📋 جولة الاختيار رقم {session['round']}",
        description=f"الدور الآن عندك يا كابتن: {captain_member.mention}\n"
                    f"الرجاء اختيار لاعبيك المفضلين من القائمة بالأسفل.\n\n"
                    f"✨ *ميزة ذكية: القائمة مدعومة بالتحديث التلقائي اللحظي فور استخدامها.*\n\n"
                    f"⚡ حصتك المتاحة في هذا الدور: **{picks_allowed} لاعبين** دفعة واحدة.",
        color=discord.Color.blue()
    )
    await channel.send(content=captain_member.mention, embed=embed, view=DraftView(guild, picks_allowed))

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

    session["active"] = True
    session["captains"] = chosen_caps
    session["current_index"] = 0
    session["round"] = 1
    session["picks_allowed"] = 2

    await interaction.response.send_message(f" **بدأ نظام التقسيم التلقائي بنجاح لـ {عدد_الفرق} فرق!**")
    
    await send_next_turn(interaction.channel, interaction.guild)

# --- أمر تعديل الاختيارات/المراكز المحدث والمضمون للظهور فوراً ---
@bot.tree.command(name="تعديل_الاختيارات", description="تعديل عدد اللاعبين المتاح اختيارهم للكباتن في الدور الحالي والأدوار القادمة")
@app_commands.describe(العدد="أدخل عدد الاختيارات المطلوب للتحكم بالعدد والمراكز (مثال: 3 أو 2)")
@app_commands.default_permissions(use_application_commands=True)
async def تعديل_الاختيارات(interaction: discord.Interaction, العدد: int):
    if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
        await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص فقط لمن يحمل رتبة المسؤول عن التقسيمة!", ephemeral=True)
        return

    if العدد < 1 or العدد > 23:
        await interaction.response.send_message("❌ الرجاء إدخال عدد صحيح ومنطقي (بين 1 و 23).", ephemeral=True)
        return

    session["picks_allowed"] = العدد
    await interaction.response.send_message(f"⚙️ **تحديث الإعدادات:** تم تعديل حصة الاختيار والمراكز بنجاح! الدور القادم وكل الأدوار القادمة ستسمح للكباتن باختيار **{العدد} لاعبين** دفعة واحدة.")

# --- أمر التحديث الإجباري العادي بالشات ---
@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("🔄 تم إجبار ديسكورد على تحديث ومزامنة جميع الأوامر المائلة المضافة حديثاً بما فيها تعديل الاختيارات!")

# تشغيل البوت
token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("Error: DISCORD_TOKEN is missing.")
