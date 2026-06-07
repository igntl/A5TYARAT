require('dotenv').config();
const { Client, GatewayIntentBits, Partials, ActionRowBuilder, StringSelectMenuBuilder, REST, Routes, SlashCommandBuilder } = require('discord.js');

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.GuildVoiceStates],
  partials: [Partials.Channel]
});

// ===== CONFIG =====
const IDs = {
  guildId: '1475334188826759319',        // ID السيرفر
  adminRole: '1475334752436359320',     // رتبة المسؤول
  voiceRoom: '1513180587584782446',     // روم التقسيمة
  captainRoles: ['1490247564086214787', '1495426762971283528'], // الحزام / كابيتانو
  captainVoiceRooms: [
    '1475334190034587661', // روم كابتن 1
    '1483219750027919422', // روم كابتن 2
    'ROOM_ID_3',
    'ROOM_ID_4',
    'ROOM_ID_5',
    'ROOM_ID_6'
  ]
};

// ===== STATE =====
let state = {
  numTeams: 0,
  captains: [],
  playersPool: [],
  turnIndex: 0
};

// ===== REGISTER GUILD SLASH COMMAND =====
client.once('ready', async () => {
  console.log(`Logged in as ${client.user.tag}`);

  const commands = [
    new SlashCommandBuilder()
      .setName('startdivision')
      .setDescription('ابدأ تقسيمة FIFA Pro Club')
      .toJSON()
  ];

  const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
  await rest.put(
    Routes.applicationGuildCommands(client.user.id, IDs.guildId),
    { body: commands }
  );

  console.log('Slash command /startdivision registered for this guild.');
});

// ===== HANDLE INTERACTIONS =====
client.on('interactionCreate', async (interaction) => {
  if (interaction.isChatInputCommand() && interaction.commandName === 'startdivision') {
    if (!interaction.member.roles.cache.has(IDs.adminRole)) {
      return interaction.reply({ content: 'ليس لديك صلاحية بدء التقسيمة.', ephemeral: true });
    }

    state = { numTeams: 0, captains: [], playersPool: [], turnIndex: 0 };

    // Dropdown لاختيار عدد الفرق
    const row = new ActionRowBuilder().addComponents(
      new StringSelectMenuBuilder()
        .setCustomId('select_teams')
        .setPlaceholder('اختر عدد الفرق')
        .addOptions([
          { label: '2 فرق', value: '2' },
          { label: '4 فرق', value: '4' },
          { label: '6 فرق', value: '6' }
        ])
    );

    await interaction.reply({ content: 'اختر عدد الفرق:', components: [row] });
    return;
  }

  if (!interaction.isStringSelectMenu()) return;

  // اختيار عدد الفرق
  if (interaction.customId === 'select_teams') {
    state.numTeams = parseInt(interaction.values[0]);
    const vcChannel = await interaction.guild.channels.fetch(IDs.voiceRoom);

    // استخدام Nickname وليس username
    state.playersPool = vcChannel.members.map(m => m.nickname || m.user.username);

    const captainOptions = state.playersPool.map(name => ({ label: name, value: name }));
    const row = new ActionRowBuilder().addComponents(
      new StringSelectMenuBuilder()
        .setCustomId('select_captains')
        .setPlaceholder(`اختر الكابتن 1 من ${state.playersPool.length} لاعبين`)
        .setMaxValues(1)
        .addOptions(captainOptions)
    );

    await interaction.update({ content: `تم اختيار ${state.numTeams} فرق.\nاختر الكباتن بالترتيب:`, components: [row] });
    return;
  }

  // اختيار الكباتن
  if (interaction.customId === 'select_captains') {
    const chosen = interaction.values[0];
    state.captains.push(chosen);
    state.playersPool = state.playersPool.filter(p => p !== chosen);
    state.turnIndex = 0;

    if (state.captains.length < state.numTeams) {
      const nextOptions = state.playersPool.map(name => ({ label: name, value: name }));
      const row = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
          .setCustomId('select_captains')
          .setPlaceholder(`اختر الكابتن ${state.captains.length + 1}`)
          .setMaxValues(1)
          .addOptions(nextOptions)
      );
      await interaction.update({ content: `اختر الكابتن التالي:`, components: [row] });
    } else {
      await interaction.update({ content: `تم اختيار جميع الكباتن: ${state.captains.join(', ')}\nابدأ اختيار اللاعبين:`, components: [] });
      startPlayerPick(interaction);
    }
    return;
  }

  // اختيار اللاعبين
  if (interaction.customId.startsWith('pick_player_')) {
    const captainName = interaction.customId.split('_')[2];
    const selectedPlayer = interaction.values[0];

    const captainIndex = state.captains.indexOf(captainName);
    const vcChannel = await interaction.guild.channels.fetch(IDs.voiceRoom);
    const member = vcChannel.members.find(m => (m.nickname || m.user.username) === selectedPlayer);
    if (member) {
      const targetRoomId = IDs.captainVoiceRooms[captainIndex];
      const targetRoom = await interaction.guild.channels.fetch(targetRoomId);
      await member.voice.setChannel(targetRoom);
    }

    state.playersPool = state.playersPool.filter(p => p !== selectedPlayer);
    state.turnIndex = (state.turnIndex + 1) % state.captains.length;

    if (state.playersPool.length > 0) {
      startPlayerPick(interaction);
    } else {
      const endRow = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
          .setCustomId('end_division')
          .setPlaceholder('إنهاء التقسيمة')
          .addOptions([{ label: 'إنهاء التقسيمة', value: 'end' }])
      );
      await interaction.update({ content: 'تم اختيار جميع اللاعبين!', components: [endRow] });
    }
    return;
  }

  // إنهاء التقسيمة
  if (interaction.customId === 'end_division') {
    state = { numTeams: 0, captains: [], playersPool: [], turnIndex: 0 };
    await interaction.update({ content: 'تم إعادة تهيئة البوت للتقسيمة القادمة.', components: [] });
    return;
  }
});

// ===== FUNCTIONS =====
async function startPlayerPick(interaction) {
  const currentCaptain = state.captains[state.turnIndex];
  const options = state.playersPool.map(name => ({ label: name, value: name }));

  const row = new ActionRowBuilder().addComponents(
    new StringSelectMenuBuilder()
      .setCustomId(`pick_player_${currentCaptain}`)
      .setPlaceholder(`دور ${currentCaptain} لاختيار لاعب`)
      .setMaxValues(1)
      .addOptions(options)
  );

  await interaction.followUp({ content: `دور ${currentCaptain} لاختيار لاعب:`, components: [row] });
}

// ===== LOGIN =====
client.login(process.env.DISCORD_TOKEN);
