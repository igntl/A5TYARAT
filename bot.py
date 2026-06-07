import discord
from discord.ext import commands
from discord import app_commands
import asyncio
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

# --- إعدادات البوت ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

class ProClubBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        await self.tree.sync()
        print("⚽ تم تشغيل بوت البرو كلوب المطور بنجاح!")

bot = ProClubBot()
session = {} # ذاكرة الجلسة الحالية للتقسيمة

# --- دالة مساعدة لتقسيم القوائم إلى صفحات ---
def get_page_options(members_list, page=0, per_page=23):
    start = page * per_page
    end = start + per_page
    sub_list = members_list[start:end]
    
    options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in sub_list]
    
    if page > 0:
        options.insert(0, discord.SelectOption(label="⬅️ الصفحة السابقة", value="prev_page"))
    if end < len(members_list):
        options.append(discord.SelectOption(label="➡️ الصفحة التالية", value="next_page"))
        
    if not options:
        options.append(discord.SelectOption(label="لا يوجد لاعبين متاحين حالياً", value="none"))
    return options

# --- واجهة اختيار اللاعبين للكباتن (The Draft) ---
class PlayerSelectMenu(discord.ui.Select):
    def __init__(self, lobby_members, max_values=1, page=0):
        self.page = page
        self.lobby_members = lobby_members
        self.max_values = max_values
        options = get_page_options(lobby_members, page)
        super().__init__(
            placeholder="اختر اللاعبين لنقلهم إلى رومك الصوتي...",
            min_values=1,
            max_values=min(max_values, len(options)),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        expected_captain = session["captains"][session["current_captain_index"]]
        if interaction.user.id != expected_captain:
            await interaction.response.send_message("❌ ليس دورك في الاختيار الآن! انتظر دورك المخصص.", ephemeral=True)
            return

        val = self.values[0]
        if val == "next_page":
            await interaction.response.edit_message(view=PlayerDraftView(self.lobby_members, self.max_values, self.page + 1))
            return
        elif val == "prev_page":
            await interaction.response.edit_message(view=PlayerDraftView(self.lobby_members, self.max_values, self.page - 1))
            return
        elif val == "none":
            return

        await interaction.response.defer()
        
        selected_ids = [int(v) for v in self.values if v not in ["next_page", "prev_page"]]
        target_voice_id = TEAM_CHANNELS[session["current_captain_index"]]
        target_voice_channel = interaction.guild.get_channel(target_voice_id)

        # سحب اللاعبين المختارين فورا إلى روم الكابتن المحدد
        if target_voice_channel:
            for p_id in selected_ids:
                if p_id in session["players_pool"]:
                    session["players_pool"].remove(p_id)
                    member = interaction.guild.get_member(p_id)
                    if member and member.voice and member.voice.channel:
                        try:
                            await member.move_to(target_voice_channel)
                        except:
                            pass

        # نقل الدور للكابتن التالي وتنبيهه
        session["current_captain_index"] += 1
        if session["current_captain_index"] >= len(session["captains"]):
            session["current_captain_index"] = 0
            session["round_number"] += 1 # الانتقال للجولة التالية لجميع الكباتن
            
        session["event"].set()

class PlayerDraftView(discord.ui.View):
    def __init__(self, lobby_members, max_values=1, page=0):
        super().__init__(timeout=40)
        self.add_item(PlayerSelectMenu(lobby_members, max_values, page))

# --- واجهة إنهاء وإعادة تهيئة التقسيمة ---
class ResetSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label="🏁 إنهاء التقسيمة وإعادة التهيئة", value="reset_all")]
        super().__init__(placeholder="خيارات المسؤول لإغلاق وإعادة تهيئة البوت...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
            await interaction.response.send_message("❌ هذا الخيار مخصص للمسؤولين فقط.", ephemeral=True)
            return
            
        session.clear()
        embed = discord.Embed(
            title="🏁 تم إنهاء التقسيمة",
            description="تمت إعادة تهيئة البوت بالكامل بنجاح وهو جاهز الآن لاستقبال تقسيمة جديدة.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class ResetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ResetSelect())

# --- محرك إدارة جولات التقسيم المباشر والسريع ---
async def run_draft_engine(interaction: discord.Interaction):
    guild = interaction.guild
    channel = interaction.channel

    # انتظر ثانية واحدة للتأكد من استقرار إرسال رسالة البداية
    await asyncio.sleep(1)

    while session["players_pool"]:
        # تحديث قائمة المتواجدين في الروم الصوتي باستمرار لمنع الأخطاء
        lobby_channel = guild.get_channel(LOBBY_VOICE_ID)
        current_lobby_ids = [m.id for m in lobby_channel.members] if lobby_channel else []
        session["players_pool"] = [p for p in session["players_pool"] if p in current_lobby_ids]

        if not session["players_pool"]:
            break

        idx = session["current_captain_index"]
        cap_id = session["captains"][idx]
        captain_member = guild.get_member(cap_id)

        if not captain_member:
            session["current_captain_index"] += 1
            if session["current_captain_index"] >= len(session["captains"]):
                session["current_captain_index"] = 0
                session["round_number"] += 1
            continue

        # حساب ميزات الرتب الخاصة (الحزام أو كابيتانو)
        has_special_role = any(r.id in [ROLE_HEZAM_ID, ROLE_CAPITANO_ID] for r in captain_member.roles)
        if has_special_role:
            if session["round_number"] == 1:
                max_pick = 3
            elif session["round_number"] == 2:
                max_pick = 1
            else:
                max_pick = 2
        else:
            max_pick = 1

        session["event"] = asyncio.Event()
        
        # جلب الكائنات البرمجية للاعبين المتاحين حالياً
        available_members = []
        for p_id in session["players_pool"]:
            m = guild.get_member(p_id)
            if m:
                available_members.append(m)

        if not available_members:
            break

        view = PlayerDraftView(available_members, max_values=max_pick)
        
        embed = discord.Embed(
            title=f"📋 جولة الاختيار رقم {session['round_number']}",
            description=f"الدور الآن عند الكابتن: {captain_member.mention}\n"
                        f"يرجى فتح القائمة بالأسفل واختيار لاعبيك. لديك **30 ثانية** فقط.\n\n"
                        f"⚡ حصتك المتاحة في هذا الدور: **{max_pick} لاعبين**.",
            color=discord.Color.blue()
        )
        
        draft_msg = await channel.send(content=captain_member.mention, embed=embed, view=view)

        # تايمر الـ 30 ثانية
        try:
            await asyncio.wait_for(session["event"].wait(), timeout=30.0)
        except asyncio.TimeoutError:
            if session["players_pool"]:
                import random
                auto_picks = random.sample(session["players_pool"], min(max_pick, len(session["players_pool"])))
                target_voice_id = TEAM_CHANNELS[idx]
                target_voice_channel = guild.get_channel(target_voice_id)
                
                if target_voice_channel:
                    for p_id in auto_picks:
                        if p_id in session["players_pool"]:
                            session["players_pool"].remove(p_id)
                            member = guild.get_member(p_id)
                            if member and member.voice and member.voice.channel:
                                try:
                                    await member.move_to(target_voice_channel)
                                except:
                                    pass
                await channel.send(f"⏱️ **انتهى الوقت!** قام البوت بسحب لاعبين عشوائيين لفريق الكابتن {captain_member.mention}.")
            
            session["current_captain_index"] += 1
            if session["current_captain_index"] >= len(session["captains"]):
                session["current_captain_index"] = 0
                session["round_number"] += 1

        try:
            await draft_msg.delete()
        except:
            pass

    # عند انتهاء اللاعبين بالكامل
    embed_end = discord.Embed(
        title="🎉 تم توزيع جميع اللاعبين بنجاح!",
        description="انتهت عملية التقسيم بالكامل، يتوجب على المسؤول الآن الضغط بالأسفل لإعادة تهيئة البوت.",
        color=discord.Color.green()
    )
    await channel.send(embed=embed_end, view=ResetView())

# --- الأمر المائل الأساسي السريع ---
@bot.tree.command(name="تقسيم", description="بدء جولات اختيار وتقسيم لاعبي البرو كلوب بالترتيب")
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
    # 1. التحقق من رتبة المسؤول
    if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
        await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص فقط لمن يحمل رتبة المسؤول عن التقسيمة!", ephemeral=True)
        return

    # 2. التحقق من شات البوت المخصص
    if interaction.channel_id != TEXT_CHANNEL_ID:
        await interaction.response.send_message(f"❌ هذا الأمر يعمل فقط داخل شات البوت المخصص: <#{TEXT_CHANNEL_ID}>", ephemeral=True)
        return

    # 3. التحقق من عدد الفرق
    if عدد_الفرق not in [2, 4, 6]:
        await interaction.response.send_message("❌ الرجاء اختيار عدد فرق صحيح (2 أو 4 أو 6 فقط).", ephemeral=True)
        return

    await interaction.response.defer()

    # 4. تجميع الكباتن المدخلين
    all_caps = [كابتن_1, كابتن_2, كابتن_3, كابتن_4, كابتن_5, كابتن_6]
    captains_list = [c.id for c in all_caps[:عدد_الفرق] if c is not None]

    if len(captains_list) != عدد_الفرق:
        await interaction.followup.send(f"❌ خطأ: قمت بتحديد {عدد_الفرق} فرق ولكن لم تدخل كباتن كافيين بالترتيب.", ephemeral=True)
        return

    # 5. جلب الأعضاء المتواجدين بالروم الصوتي
    guild = interaction.guild
    lobby_channel = guild.get_channel(LOBBY_VOICE_ID)
    
    if not lobby_channel or not lobby_channel.members:
        await interaction.followup.send("❌ روم التقسيمة الصوتي فارغ حالياً أو لم يتم العثور عليه!", ephemeral=True)
        return

    # فرز وتجهيز قائمة اللاعبين المتاحين (باستثناء الكباتن)
    players_pool = [m.id for m in lobby_channel.members if m.id not in captains_list]

    # بدء الجلسة
    session.clear()
    session.update({
        "guild": guild,
        "captains": captains_list,
        "players_pool": players_pool,
        "current_captain_index": 0,
        "round_number": 1,
        "event": None
    })

    await interaction.followup.send(f"🎬 **بدأت جولات التقسيم الفورية بالتناوب لـ {عدد_الفرق} فرق!**")
    
    # تشغيل محرك الدرفت المباشر فوراً
    bot.loop.create_task(run_draft_engine(interaction))

# تشغيل البوت
token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("Error: DISCORD_TOKEN variable not found.")
