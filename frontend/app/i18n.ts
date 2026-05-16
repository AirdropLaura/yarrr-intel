// Lightweight i18n for Yarrr.Tech.
// ID is default (Indonesian-speaking founder, primary audience), EN is opt-in.
// Technical Web3 terms stay English in both locales (smart money, swap, bridge, etc.).

export type Lang = 'id' | 'en';

export const DEFAULT_LANG: Lang = 'id';

export type Dict = {
  // header
  taglineVersion: string;
  github: string;
  // hero
  betaBadge: string;
  heroTitleA: string;
  heroTitleB: string;
  heroSub: string;
  // intro / about
  introHeading: string;
  introBody: string;
  builtBy: string;
  builtByName: string;
  builtByRole: string;
  // input
  placeholder: string;
  analyze: string;
  analyzing: string;
  tryLabel: string;
  scanning: string;
  interpreting: string;
  // output panel
  walletIntel: string;
  analysisComplete: string;
  reasoning: string;
  // errors
  errorPrefix: string;
  invalidAddress: string;
  // examples
  exVitalik: string;
  exSmart: string;
  exCZ: string;
  exYarrr: string;
  // features section
  featuresHeading: string;
  feat1Title: string;  feat1Desc: string;
  feat2Title: string;  feat2Desc: string;
  feat3Title: string;  feat3Desc: string;
  feat4Title: string;  feat4Desc: string;
  feat5Title: string;  feat5Desc: string;
  feat6Title: string;  feat6Desc: string;
  // footer
  footerOperated: string;
  footerBuilt: string;
  // digest panel
  digestTitle: string;
  archetypeTitle: string;
  archetypeNone: string;
  fundingTitle: string;
  fundingCex: string;
  fundingBridge: string;
  fundingClaim: string;
  confStrong: string;
  confModerate: string;
  confTentative: string;
  shareBtn: string;
  shareCopied: string;
  shareError: string;
  timelineTitle: string;
  timelineLegendBridge: string;
  timelineLegendDex: string;
  timelineLegendOther: string;
  timelineLegendError: string;
  reputationTitle: string;
  reputationSubtitle: string;
  repContribTitle: string;
  repNoContribs: string;
  repBucketHigh: string;
  repBucketGood: string;
  repBucketNeutral: string;
  repBucketLow: string;
  repBucketPoor: string;
  modeSingle: string;
  modeMulti: string;
  multiPlaceholder: string;
  multiHint: string;
  multiAnalyze: string;
  multiMinAddrs: string;
  multiMaxAddrs: string;
  clusterTitle: string;
  clusterSubtitle: string;
  clusterSiblings: string;
  clusterSources: string;
  clusterMatches: string;
  clusterDisclaimer: string;
  tokensTitle: string;
  tokensStable: string;
  tokensERC20: string;
  tokensNFT: string;
  tokensSpam: string;
  tokensLP: string;
  tokensLST: string;
  failedClustersTitle: string;
  failedClustersHint: string;
  statTotalTx: string;
  statErrorRate: string;
  statFirstSeen: string;
  statLastSeen: string;
  statAge: string;
  partialWarning: string;
  nativeBalances: string;
  // Asset trust (Phase 4)
  assetTrustTitle: string;
  assetTrustHint: string;
  trustedAssets: string;
  uncertainAssets: string;
  spamAssets: string;
  spamHint: string;
  tokenHoldings: string;
  tokenHoldingsHint: string;
  spamHoldings: string;
  activityCategories: string;
  heuristicFlags: string;
  topContracts: string;
  chainsMainnet: string;
  chainsTestnet: string;
  // age units (compact, fit pill chips)
  ageHour: string;
  ageDay: string;
  ageMonth: string;
  ageYear: string;
  // language switcher
  langLabel: string;
  langID: string;
  langEN: string;
};

export const T: Record<Lang, Dict> = {
  id: {
    taglineVersion: 'v0.10 · powered by MiMo V2.5',
    github: 'GitHub',

    betaBadge: 'Gratis selama beta',
    heroTitleA: 'Pahami wallet apa pun',
    heroTitleB: 'secara instan.',
    heroSub: 'Tempelkan satu atau beberapa alamat EVM. AI membaca riwayat on-chain di 22 mainnet + 15 testnet dan menjelaskan apa yang sebenarnya wallet itu lakukan — bukan sekadar saldo.',

    introHeading: 'Tentang Yarrr.Tech',
    introBody: 'Yarrr.Tech adalah layanan AI Wallet Intelligence yang memadatkan ratusan transaksi dari 22 EVM mainnet + 15 testnet menjadi satu laporan singkat. Bukan portfolio tracker — kami menjelaskan apa yang wallet itu lakukan: airdrop hunter, smart money, dormant whale, NFT trader, atau MEV bot. Dibangun di atas Xiaomi MiMo V2.5, berjalan di satu VPS, dengan teliti.',
    builtBy: 'Dibangun oleh',
    builtByName: 'Bastiar',
    builtByRole: 'Developer & operator',

    placeholder: '0x... alamat wallet',
    analyze: 'Analisis →',
    analyzing: 'Menganalisis…',
    tryLabel: 'Coba:',
    scanning: 'Memindai Ethereum, Polygon, Arbitrum, Base, Optimism…',
    interpreting: 'AI sedang menginterpretasi wallet…',

    walletIntel: 'Wallet Intel',
    analysisComplete: 'analisis selesai',
    reasoning: 'Bernalar…',

    errorPrefix: 'Error:',
    invalidAddress: 'Tempelkan alamat EVM 0x… yang valid.',

    exVitalik: 'OG · DeFi multi-chain',
    exSmart: 'Henrik Andersson',
    exCZ: 'Pendiri Binance',
    exYarrr: 'Coba pakai milikmu',

    featuresHeading: 'Yang kami sampaikan tentang sebuah wallet',
    feat1Title: 'Behavioral profile',
    feat1Desc: 'Smart money, airdrop hunter, dormant whale, NFT trader, MEV searcher — operator macam apa yang menjalankan wallet ini.',
    feat2Title: 'Chain footprint',
    feat2Desc: 'Di mana aktivitas sebenarnya hidup. Hub utama vs. chain pinggiran. Titik masuk bridge.',
    feat3Title: 'Notable findings',
    feat3Desc: 'Pergerakan terbaru yang tidak biasa, target berulang, perubahan dormant→active, aliran besar yang patut diperhatikan.',
    feat4Title: 'Risk signals',
    feat4Desc: 'Tingkat error tinggi, revert berulang, counterparty unverified, pola mencurigakan.',
    feat5Title: 'Activity categories',
    feat5Desc: 'DEX swaps, NFT mints, bridges, lending, governance, claims — dihitung dan diklasifikasikan.',
    feat6Title: 'Bottom-line summary',
    feat6Desc: 'Satu paragraf yang bisa kamu kirim ke teman supaya dia benar-benar paham wallet itu.',

    footerOperated: 'yarrr-node.com · dioperasikan oleh',
    footerBuilt: 'dibangun di satu VPS, dengan teliti',

    digestTitle: 'Ringkasan on-chain',
    archetypeTitle: 'Archetype kandidat',
    archetypeNone: 'Belum ada sinyal archetype yang cukup kuat. AI tetap akan menafsirkan profil wallet di laporan.',
    fundingTitle: 'Sumber pendanaan (heuristik)',
    fundingCex: 'Setoran dari CEX',
    fundingBridge: 'Bridge inbound',
    fundingClaim: 'Airdrop claim',
    confStrong: 'kuat',
    confModerate: 'sedang',
    confTentative: 'tentatif',
    shareBtn: 'Bagikan analisis',
    shareCopied: 'Tautan disalin',
    shareError: 'Gagal bagikan — coba lagi',
    timelineTitle: 'Timeline aktivitas',
    timelineLegendBridge: 'bridge',
    timelineLegendDex: 'swap / DEX',
    timelineLegendOther: 'lain-lain',
    timelineLegendError: 'rasio error tinggi',
    reputationTitle: 'Skor reputasi',
    reputationSubtitle: 'sinyal komposit · 0-100',
    repContribTitle: 'Kontribusi utama',
    repNoContribs: 'Belum ada sinyal mencolok — skor mendekati baseline.',
    repBucketHigh: 'tinggi',
    repBucketGood: 'baik',
    repBucketNeutral: 'netral',
    repBucketLow: 'rendah',
    repBucketPoor: 'buruk',
    modeSingle: 'Satu wallet',
    modeMulti: 'Multi wallet',
    multiPlaceholder: 'Tempel beberapa alamat (pisahkan dengan baris baru, koma, atau spasi)\n0x85B395f1511d3c14Ad984F02B2C4fbd7E56D0957\n0x1ce444466940637B0FcFe8a4543c9Bb6f2c2FcB1',
    multiHint: '2-10 alamat. AI akan membandingkan dan mencari pola lintas wallet.',
    multiAnalyze: 'Bandingkan',
    multiMinAddrs: 'Minimum 2 alamat untuk analisis multi.',
    multiMaxAddrs: 'Maksimum 10 alamat per batch.',
    clusterTitle: 'Sinyal sybil graph',
    clusterSubtitle: 'wallet dengan funding mirip',
    clusterSiblings: 'Sibling wallet',
    clusterSources: 'Sumber bersama',
    clusterMatches: 'Hasil pencocokan',
    clusterDisclaimer: 'Korelasi, bukan kepastian. Wallet bisa share funding source secara kebetulan.',
    tokensTitle: 'Aktivitas token',
    tokensStable: 'Volume stablecoin',
    tokensERC20: 'ERC20 berbeda',
    tokensNFT: 'Koleksi NFT',
    tokensSpam: 'Spam NFT diterima',
    tokensLP: 'LP token',
    tokensLST: 'Liquid staking token',
    failedClustersTitle: 'Pola revert berulang',
    failedClustersHint: 'Saat sebuah wallet menabrak target sama dengan call yang sama dan terus revert, biasanya ini failed mint, slippage, atau permit timing. Analyst akan menginterpretasi.',
    statTotalTx: 'Total tx',
    statErrorRate: 'Tingkat error',
    statFirstSeen: 'Pertama',
    statLastSeen: 'Terakhir',
    statAge: 'Umur wallet',
    partialWarning: 'Sebagian data ({n} chain) tidak lengkap karena Etherscan rate-limit. Coba ulangi sebentar lagi untuk hasil penuh.',
    nativeBalances: 'Saldo native',
    assetTrustTitle: 'Kepercayaan aset',
    assetTrustHint: '(klasifikasi token)',
    trustedAssets: 'Aset terverifikasi',
    uncertainAssets: 'Kepercayaan rendah',
    spamAssets: 'Token spam tersembunyi',
    spamHint: 'klik untuk membuka',
    tokenHoldings: 'Token holdings',
    tokenHoldingsHint: '(perkiraan dari net flow)',
    spamHoldings: 'Token spam tersembunyi ({n})',
    activityCategories: 'Kategori aktivitas',
    heuristicFlags: 'Flag heuristik',
    topContracts: 'Kontrak counterparty teratas',
    chainsMainnet: 'Mainnet aktif',
    chainsTestnet: 'Testnet aktif',

    ageHour: 'j lalu',
    ageDay: 'h lalu',
    ageMonth: 'bln lalu',
    ageYear: 'thn lalu',

    langLabel: 'Bahasa',
    langID: 'Bahasa Indonesia',
    langEN: 'English',
  },
  en: {
    taglineVersion: 'v0.10 · powered by MiMo V2.5',
    github: 'GitHub',

    betaBadge: 'Free during beta',
    heroTitleA: 'Understand any wallet',
    heroTitleB: 'instantly.',
    heroSub: 'Paste one or many EVM wallet addresses. AI reads on-chain history across 22 mainnets + 15 testnets and tells you what they actually do — not just balances.',

    introHeading: 'About Yarrr.Tech',
    introBody: 'Yarrr.Tech is an AI Wallet Intelligence service that compresses hundreds of transactions across 22 EVM mainnets + 15 testnets into a single concise report. Not a portfolio tracker — we tell you what the wallet actually does: airdrop hunter, smart money, dormant whale, NFT trader, or MEV bot. Built on Xiaomi MiMo V2.5, running on a single VPS, with care.',
    builtBy: 'Built by',
    builtByName: 'Bastiar',
    builtByRole: 'Developer & operator',

    placeholder: '0x... wallet address',
    analyze: 'Analyze →',
    analyzing: 'Analyzing…',
    tryLabel: 'Try:',
    scanning: 'Scanning Ethereum, Polygon, Arbitrum, Base, Optimism…',
    interpreting: 'AI is interpreting the wallet…',

    walletIntel: 'Wallet Intel',
    analysisComplete: 'analysis complete',
    reasoning: 'Reasoning…',

    errorPrefix: 'Error:',
    invalidAddress: 'Please paste a valid 0x… EVM address.',

    exVitalik: 'OG · multi-chain DeFi',
    exSmart: 'Henrik Andersson',
    exCZ: 'Binance founder',
    exYarrr: 'Try with your own',

    featuresHeading: 'What we tell you about a wallet',
    feat1Title: 'Behavioral profile',
    feat1Desc: 'Smart money, airdrop hunter, dormant whale, NFT trader, MEV searcher — what kind of operator runs this wallet.',
    feat2Title: 'Chain footprint',
    feat2Desc: 'Where the activity actually lives. Primary hub vs. peripheral chains. Bridge entry points.',
    feat3Title: 'Notable findings',
    feat3Desc: 'Unusual recent moves, repeated targets, dormant→active shifts, large flows worth attention.',
    feat4Title: 'Risk signals',
    feat4Desc: 'High error rate, repeated reverts, unverified counterparties, suspicious patterns.',
    feat5Title: 'Activity categories',
    feat5Desc: 'DEX swaps, NFT mints, bridges, lending, governance, claims — counted and classified.',
    feat6Title: 'Bottom-line summary',
    feat6Desc: 'One paragraph you could send to a friend so they actually understand the wallet.',

    footerOperated: 'yarrr-node.com · operated by',
    footerBuilt: 'built on a single VPS, with care',

    digestTitle: 'On-chain digest',
    archetypeTitle: 'Archetype candidates',
    archetypeNone: 'No archetype signal strong enough yet. AI will still interpret the wallet profile in the report.',
    fundingTitle: 'Funding source (heuristic)',
    fundingCex: 'CEX deposit',
    fundingBridge: 'Bridge inbound',
    fundingClaim: 'Airdrop claim',
    confStrong: 'strong',
    confModerate: 'moderate',
    confTentative: 'tentative',
    shareBtn: 'Share analysis',
    shareCopied: 'Link copied',
    shareError: 'Share failed — try again',
    timelineTitle: 'Activity timeline',
    timelineLegendBridge: 'bridge',
    timelineLegendDex: 'swap / DEX',
    timelineLegendOther: 'other',
    timelineLegendError: 'high error rate',
    reputationTitle: 'Reputation score',
    reputationSubtitle: 'composite signal · 0-100',
    repContribTitle: 'Top contributions',
    repNoContribs: 'No notable signals — score sits near baseline.',
    repBucketHigh: 'high',
    repBucketGood: 'good',
    repBucketNeutral: 'neutral',
    repBucketLow: 'low',
    repBucketPoor: 'poor',
    modeSingle: 'Single wallet',
    modeMulti: 'Multi wallet',
    multiPlaceholder: 'Paste multiple addresses (separate by newline, comma, or space)\n0x85B395f1511d3c14Ad984F02B2C4fbd7E56D0957\n0x1ce444466940637B0FcFe8a4543c9Bb6f2c2FcB1',
    multiHint: '2-10 addresses. AI will compare and find cross-wallet patterns.',
    multiAnalyze: 'Compare',
    multiMinAddrs: 'Minimum 2 addresses required for multi analysis.',
    multiMaxAddrs: 'Maximum 10 addresses per batch.',
    clusterTitle: 'Sybil graph signal',
    clusterSubtitle: 'wallets with overlapping funding',
    clusterSiblings: 'Sibling wallets',
    clusterSources: 'Shared sources',
    clusterMatches: 'Matches',
    clusterDisclaimer: 'Correlation, not certainty. Wallets can share funding sources by coincidence.',
    tokensTitle: 'Token activity',
    tokensStable: 'Stablecoin volume',
    tokensERC20: 'Distinct ERC20s',
    tokensNFT: 'NFT collections',
    tokensSpam: 'Spam NFTs received',
    tokensLP: 'LP tokens',
    tokensLST: 'Liquid staking tokens',
    failedClustersTitle: 'Repeated revert patterns',
    failedClustersHint: 'When a wallet hits the same target with the same call repeatedly and reverts, it usually means failed mints, slippage, or permit timing. The analyst can interpret.',
    statTotalTx: 'Total tx',
    statErrorRate: 'Error rate',
    statFirstSeen: 'First seen',
    statLastSeen: 'Last seen',
    statAge: 'Wallet age',
    partialWarning: 'Some data ({n} chains) is incomplete due to Etherscan rate limits. Retry shortly for full results.',
    nativeBalances: 'Native balances',
    assetTrustTitle: 'Asset trust',
    assetTrustHint: '(token classification)',
    trustedAssets: 'Trusted Assets',
    uncertainAssets: 'Low Confidence',
    spamAssets: 'Hidden Spam Tokens',
    spamHint: 'click to expand',
    tokenHoldings: 'Token holdings',
    tokenHoldingsHint: '(estimated from net flow)',
    spamHoldings: 'Hidden spam tokens ({n})',
    activityCategories: 'Activity categories',
    heuristicFlags: 'Heuristic flags',
    topContracts: 'Top counterparty contracts',
    chainsMainnet: 'Active mainnets',
    chainsTestnet: 'Active testnets',

    ageHour: 'h ago',
    ageDay: 'd ago',
    ageMonth: 'mo ago',
    ageYear: 'y ago',

    langLabel: 'Language',
    langID: 'Bahasa Indonesia',
    langEN: 'English',
  },
};
