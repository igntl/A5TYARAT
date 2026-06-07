// index.js - بوت تقسيمات FIFA Pro Club تفاعلي
const { Client, GatewayIntentBits, Events, ActionRowBuilder, StringSelectMenuBuilder } = require('discord.js');
require('dotenv').config();

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildVoiceStates
  ]
});

// ===== CONFIG =====
const allowedChannelID = "1483219896069525665"; // شات البوت
const divisionRoomID = "1475334190034587661"; // روم التقسيمة

const teamRooms = {
  1: "1483219750027919422",
  2: "1513180587584782446",
  3: "ROOM_ID_3",
  4: "ROOM_ID_4",
  5: "ROOM_ID_5",
  6: "ROOM_ID_6"
};

const specialRanks = {
  capitan: "1495426762971283528",
  belt: "1490247564086214787"
};

const divisionManagerRoleID = "1475334752436359320"; // رول مسؤول التقسيمة

// ===== STATE =====
let numberOfTeams = 0;
let captains = [];
let currentCaptainTurn = 0;
let selections = {};
let remainingPlayers = [];
let captainSelectionPhase = false;

// ===== HELPERS =====
async function getPlayersInDivision(guild) {
  const channel = guild.channels.cache.get(divisionRoomID);
  if (!channel) return [];
  return channel.members ? Array.from(channel.members.values()) : [];
}

function canSelect(userID) {
  return userID === captains[currentCaptainTurn];
}

function getMaxSelectableForCaptain(captainId) {
  const member = client.guilds.cache.first().members.cache.get(captainId);
  if (!member) return 2;
  if (member.roles.cache.has(specialRanks.capitan) || member.roles.cache.has(specialRanks.belt)) {
    if (!selections[captainId]) return 3;
    if (selections[captainId] === 3) return 1;
    return 2;
  }
  return 2;
}

// ===== SHOW DROPDOWN FOR CAPTAINS =====
async function showDropdownForCaptain(captainId) {
  const channel = client.channels.cache.get(allowedChannelID);
  const captainMember = await client.guilds.cache.first().members.fetch(captainId);

  if (remainingPlayers.length === 0) {
    channel.send("⚠️ لا يوجد لاعبين متبقين للاختيار.");
    return;
  }

  const row = new ActionRowBuilder().addComponents(
    new StringSelectMenuBuilder()
      .setCustomId('select_players')
      .setPlaceholder('اختر لاعبيك أو إنهاء الدور/التقسيمة')
      .addOptions([
        ...remainingPlayers.map(p => ({
          label: p.nickname || p.user.username,
          value: p.id
        })),
        { label: "✅ انتهيت من اختياراتي", description: "اعط الدور للكابتن التالي" },
        { label: "🛑 إنهاء التقسيمة", description: "انتهت كل الاختيارات" }
      ])
      .setMinValues(1)
      .setMaxValues(getMaxSelectableForCaptain(captainId))
  );

  channel.send({ content: `<@${captainId}> الدور عليك! اختر لاعبيك:`, components: [row] });
}

function nextCaptainTurn() {
  currentCaptainTurn++;
  const channel = client.channels.cache.get(allowedChannelID);
  if (currentCaptainTurn >= captains.length) {
    channel.send("✅ اكتملت كل الاختيارات! جميع اللاعبين تم توزيعهم.");
    currentCaptainTurn = -1;
  } else {
    showDropdownForCaptain(captains[currentCaptainTurn]);
  }
}

// ===== START COMMAND =====
client.on(Events.MessageCreate, async message => {
  if (message.channel.id !== allowedChannelID) return;
  if (!message.content.startsWith('!st')) return;

  const member = await message.guild.members.fetch(message.author.id);
  if (!member.roles.cache.has(divisionManagerRoleID)) {
    return message.reply("❌ ليس لديك صلاحية بدء التقسيمة.");
  }

  // Dropdown لاختيار عدد الفرق
  const row = new ActionRowBuilder().addComponents(
    new StringSelectMenuBuilder()
      .setCustomId('select_team_count')
      .setPlaceholder('اختر عدد الفرق')
      .addOptions([
        { label: '2 فرق', value: '2' },
        { label: '4 فرق', value: '4' },
        { label: '6 فرق', value: '6' }
      ])
  );
  message.channel.send({ content: 'اختر عدد الفرق:', components: [row] });
});

// ===== INTERACTIONS =====
client.on(Events.InteractionCreate, async interaction => {
  if (!interaction.isStringSelectMenu()) return;

  // اختيار عدد الفرق
  if (interaction.customId === 'select_team_count') {
    numberOfTeams = parseInt(interaction.values[0]);
    const allMembers = await getPlayersInDivision(interaction.guild);
    remainingPlayers = allMembers;
    captainSelectionPhase = true;

    return interaction.update({ 
      content: `✅ اختر عدد الفرق: ${numberOfTeams}\nالآن اختر ${numberOfTeams} كباتن من القائمة التالية بالترتيب:`,
      components: [new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
          .setCustomId('select_captains')
          .setPlaceholder('اختر الكباتن بالترتيب')
          .addOptions(allMembers.map(p => ({
            label: p.nickname || p.user.username,
            value: p.id
          })))
          .setMinValues(numberOfTeams)
          .setMaxValues(numberOfTeams)
      )]
    });
  }

  // اختيار الكباتن
  if (interaction.customId === 'select_captains' && captainSelectionPhase) {
    captains = interaction.values;
    selections = {};
    currentCaptainTurn = 0;
    remainingPlayers = remainingPlayers.filter(p => !captains.includes(p.id));
    captainSelectionPhase = false;

    await interaction.update({ content: `✅ تم تسجيل الكباتن بالترتيب:\n${captains.map((id,i)=>`${i+1}️⃣ <@${id}>`).join("\n")}`, components: [] });
    
    // بدء الدور للكابتن الأول بعد نصف ثانية
    setTimeout(() => {
      showDropdownForCaptain(captains[currentCaptainTurn]);
    }, 500);

    return;
  }

  // اختيار اللاعبين لكل كابتن
  if (interaction.customId === 'select_players') {
    const captainId = interaction.user.id;
    if (!canSelect(captainId)) return interaction.reply({ content: "الآن ليس دورك.", ephemeral: true });

    const selectedValues = interaction.values;

    if (selectedValues.includes("🛑 إنهاء التقسيمة")) {
      captains = [];
      selections = {};
      currentCaptainTurn = 0;
      remainingPlayers = [];
      return interaction.reply({ content: "🛑 تم إنهاء التقسيمة! يمكنك البدء من جديد.", ephemeral: true });
    }

    if (selectedValues.includes("✅ انتهيت من اختياراتي")) {
      nextCaptainTurn();
      return interaction.reply({ content: "✅ انتهى دورك، تم إعطاء الدور للكابتن التالي.", ephemeral: true });
    }

    // نقل اللاعبين المحددين
    const roomID = teamRooms[currentCaptainTurn + 1];
    for (const playerId of selectedValues) {
      const member = await interaction.guild.members.fetch(playerId);
      if (member.voice.channel) await member.voice.setChannel(roomID);
      remainingPlayers = remainingPlayers.filter(p => p.id !== playerId);
    }

    selections[captainId] = (selections[captainId] || 0) + selectedValues.length;
    await interaction.reply({ content: "✅ تم نقل اللاعبين!", ephemeral: true });

    if (selections[captainId] >= getMaxSelectableForCaptain(captainId)) {
      nextCaptainTurn();
    }
  }
});

client.login(process.env.DISCORD_TOKEN);
