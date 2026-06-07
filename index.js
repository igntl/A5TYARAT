// index.js
const { Client, GatewayIntentBits, Events } = require('discord.js');
require('dotenv').config();

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildVoiceStates
  ]
});

// ========== CONFIG ==========
const allowedChannelID = "1483219896069525665"; // الشات المسموح للبوت
const divisionRoomID = "1475334190034587661"; // روم التقسيمة نجتمع فيه

// رومات الكباتن (ضع IDs يدويًا لاحقًا)
const teamRooms = {
  1: "1483219750027919422", // روم الكابتن الأول
  2: "1513180587584782446", // روم الكابتن الثاني
  3: "ROOM_ID_3", // روم الكابتن الثالث
  4: "ROOM_ID_4", // روم الكابتن الرابع
  5: "ROOM_ID_5", // روم الكابتن الخامس
  6: "ROOM_ID_6"  // روم الكابتن السادس
};

// رتب خاصة بالبداية
const specialRanks = {
  capitan: "1495426762971283528",
  belt: "1490247564086214787"
};

// ========== STATE ==========
let numberOfTeams = 0;
let captains = []; // IDs الكباتن الحاليين
let currentCaptainTurn = 0; // دور الكابتن الحالي
let selections = {}; // عدد اختيارات كل كابتن

// ========== HELPER FUNCTIONS ==========
function isCaptain(userID) {
  return captains.includes(userID);
}

function getMaxSelections(member) {
  if (member.roles.cache.has(specialRanks.capitan) || member.roles.cache.has(specialRanks.belt)) {
    if (!selections[member.id]) return 3; // الدور الأول
    if (selections[member.id] === 3) return 1; // الدور الثاني
    return 2; // بعد ذلك طبيعي
  }
  return 2; // الكابتن العادي
}

function canSelect(userID) {
  return userID === captains[currentCaptainTurn];
}

function nextCaptainTurn(channel) {
  currentCaptainTurn++;
  if (currentCaptainTurn >= captains.length) {
    channel.send("✅ اكتملت كل الاختيارات! جميع اللاعبين تم توزيعهم.");
    currentCaptainTurn = -1;
  } else {
    channel.send(`<@${captains[currentCaptainTurn]}> الدور عليك الآن! اختر لاعبيك.`);
  }
}

// ========== GET PLAYERS IN DIVISION ROOM ==========
async function getPlayersInDivision(guild) {
  const channel = guild.channels.cache.get(divisionRoomID);
  if (!channel || !channel.isVoiceBased()) return [];
  return channel.members.map(member => member);
}

// ========== COMMAND HANDLER ==========
client.on(Events.MessageCreate, async (message) => {
  if (message.channel.id !== allowedChannelID) return;
  if (!message.content.startsWith('!')) return;

  const args = message.content.split(/\s+/);
  const command = args[0];

  // تحديد عدد الفرق
  if (command === '!f') {
    const num = parseInt(args[1]);
    if (!num || num < 2 || num > 6) return message.reply("عدد الفرق يجب أن يكون بين 2 و 6.");
    numberOfTeams = num;
    return message.reply(`✅ تم تحديد عدد الفرق: ${numberOfTeams}`);
  }

  // تحديد الكباتن
  if (command === '!c') {
    if (!numberOfTeams) return message.reply("حدد عدد الفرق أولاً بـ !f");
    if ((args.length -1) / 2 < numberOfTeams) return message.reply("حدد الكباتن مع أرقام ترتيبهم.");

    captains = [];
    selections = {};
    currentCaptainTurn = 0;

    for (let i = 1; i < args.length; i += 2) {
      const mention = args[i];
      const num = parseInt(args[i+1]);
      if (!mention.startsWith('<@') || !num) continue;
      const id = mention.replace(/\D/g,'');
      captains[num -1] = id;
      selections[id] = 0;
    }

    // عرض لائحة اللاعبين في روم التقسيمة
    const players = await getPlayersInDivision(message.guild);
    const playerList = players.map(p => `<@${p.id}>`).join(', ');
    message.reply(`✅ تم تسجيل الكباتن: ${captains.map((id,i)=>`<@${id}> (كابتن ${i+1})`).join(', ')}\n\n🎮 اللاعبين الموجودين في روم التقسيمة: ${playerList}`);
  }
});

// ========== PLAYER SELECTION ==========
client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isButton()) return;
  if (interaction.channel.id !== allowedChannelID) return;

  const userID = interaction.user.id;

  if (!canSelect(userID)) {
    return interaction.reply({ content: "الآن ليس دورك، انتظر حتى يأتي دورك.", ephemeral: true });
  }

  const member = await interaction.guild.members.fetch(userID);
  const maxSelect = getMaxSelections(member);
  if (selections[userID] >= maxSelect) {
    return interaction.reply({ content: `لقد وصلت الحد الأقصى لاختياراتك (${maxSelect})`, ephemeral: true });
  }

  const playerID = interaction.customId;
  const playerMember = await interaction.guild.members.fetch(playerID);
  const roomID = teamRooms[currentCaptainTurn + 1]; // روم الكابتن الحالي
  if (playerMember.voice.channel) {
    await playerMember.voice.setChannel(roomID);
  }

  selections[userID] += 1;
  interaction.reply({ content: `✅ تم نقل <@${playerID}> لروم الفريق`, ephemeral: true });

  if (selections[userID] >= maxSelect) {
    nextCaptainTurn(interaction.channel);
  }
});

// ========== LOGIN ==========
client.login(process.env.DISCORD_TOKEN);
