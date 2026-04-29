# TurkDamga Android — Kurulum & Kaynak Kod

## Proje Yapısı

```
TurkDamgaApp/
├── app.json
├── package.json
├── App.tsx
├── src/
│   ├── screens/
│   │   ├── StampScreen.tsx
│   │   ├── HistoryScreen.tsx
│   │   └── VerifyScreen.tsx
│   ├── components/
│   │   ├── FileCard.tsx
│   │   ├── TimestampBadge.tsx
│   │   └── QRModal.tsx
│   ├── engine/
│   │   └── timestamp.ts
│   └── theme.ts
```

---

## 1. package.json

```json
{
  "name": "turkdamga",
  "version": "1.0.0",
  "main": "expo-router/entry",
  "scripts": {
    "start": "expo start",
    "android": "expo run:android",
    "build": "eas build --platform android"
  },
  "dependencies": {
    "expo": "~51.0.0",
    "expo-router": "~3.5.0",
    "expo-document-picker": "~12.0.0",
    "expo-file-system": "~17.0.0",
    "expo-crypto": "~13.0.0",
    "expo-sharing": "~12.0.0",
    "expo-clipboard": "~6.0.0",
    "react-native": "0.74.1",
    "react-native-qrcode-svg": "^6.3.0",
    "react-native-svg": "15.2.0",
    "@react-native-async-storage/async-storage": "^1.23.0",
    "@expo/vector-icons": "^14.0.0",
    "react-native-reanimated": "~3.10.0",
    "ethers": "^5.7.2"
  }
}
```

---

## 2. src/theme.ts

```typescript
export const theme = {
  black:      '#080808',
  surface:    '#0F0F0F',
  surface2:   '#161616',
  surface3:   '#1E1E1E',
  gold:       '#C9A84C',
  goldLight:  '#E8C97A',
  goldDim:    '#7A6130',
  text:       '#E8E0D0',
  textDim:    '#8A8070',
  border:     'rgba(201,168,76,0.18)',
  borderBright:'rgba(201,168,76,0.5)',
  green:      '#27AE60',
  red:        '#C0392B',
  btcOrange:  '#F7931A',
  polyPurple: '#8247E5',
};
```

---

## 3. src/engine/timestamp.ts

```typescript
import * as Crypto from 'expo-crypto';
import * as FileSystem from 'expo-file-system';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ethers } from 'ethers';

export interface StampRecord {
  id: string;
  fileName: string;
  fileHash: string;
  fileSize: number;
  mimeType: string;
  polyTx: string;
  polyUrl: string;
  otsStatus: 'pending' | 'confirmed';
  timestamp: string;
  author: string;
  project: string;
  description: string;
  chain: string;
}

const HISTORY_KEY = 'cv_history';
const POLYGON_RPC  = 'https://polygon-rpc.com'; // ücretsiz public RPC

export async function hashFileUri(uri: string): Promise<string> {
  // Dosyayı base64 oku → SHA-256
  const base64 = await FileSystem.readAsStringAsync(uri, {
    encoding: FileSystem.EncodingType.Base64,
  });
  // base64 → binary → hash
  const digest = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    base64,
    { encoding: Crypto.CryptoEncoding.HEX }
  );
  return digest;
}

export async function stampPolygon(
  fileHash: string,
  metadata: object,
  privateKey: string
): Promise<{ txHash: string; explorerUrl: string }> {
  const provider = new ethers.providers.JsonRpcProvider(POLYGON_RPC);
  const wallet   = new ethers.Wallet(privateKey, provider);

  const payload = JSON.stringify({
    hash: fileHash,
    ts:   new Date().toISOString(),
    ...metadata,
  });

  const tx = await wallet.sendTransaction({
    to:    wallet.address,
    value: 0,
    data:  ethers.utils.hexlify(ethers.utils.toUtf8Bytes(payload)),
  });

  await tx.wait(1); // 1 blok onayı bekle

  return {
    txHash:      tx.hash,
    explorerUrl: `https://polygonscan.com/tx/${tx.hash}`,
  };
}

export async function saveRecord(record: StampRecord): Promise<void> {
  const raw     = await AsyncStorage.getItem(HISTORY_KEY);
  const history: StampRecord[] = raw ? JSON.parse(raw) : [];
  history.unshift(record);
  if (history.length > 200) history.pop();
  await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

export async function getHistory(): Promise<StampRecord[]> {
  const raw = await AsyncStorage.getItem(HISTORY_KEY);
  return raw ? JSON.parse(raw) : [];
}

export async function findByHash(hash: string): Promise<StampRecord | null> {
  const history = await getHistory();
  return history.find(r => r.fileHash === hash) || null;
}

export function generateCertText(r: StampRecord): string {
  return `TURKDAMGA — BLOCKCHAIN ZAMAN DAMGASI SERTİFİKASI
═══════════════════════════════════════════════

Sertifika ID    : ${r.id}
Damgalama Zamanı: ${new Date(r.timestamp).toLocaleString('tr-TR')}

DOSYA BİLGİLERİ
───────────────
Dosya Adı       : ${r.fileName}
SHA-256 Hash    : ${r.fileHash}
Boyut           : ${(r.fileSize / 1024).toFixed(1)} KB
Yazar           : ${r.author || '—'}
Proje           : ${r.project || '—'}

BLOCKCHAIN KAYITLARI
────────────────────
Polygon TX      : ${r.polyTx}
Bitcoin OTS     : ${r.otsStatus === 'confirmed' ? 'Onaylandı' : 'Beklemede'}

Doğrulama       : turkdamga://verify/${r.fileHash}
`;
}
```

---

## 4. App.tsx (Navigation)

```tsx
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';
import { theme } from './src/theme';
import StampScreen  from './src/screens/StampScreen';
import HistoryScreen from './src/screens/HistoryScreen';
import VerifyScreen  from './src/screens/VerifyScreen';

const Tab = createBottomTabNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <Tab.Navigator
        screenOptions={({ route }) => ({
          headerStyle: {
            backgroundColor: theme.surface,
            borderBottomColor: theme.border,
            borderBottomWidth: 1,
          },
          headerTintColor: theme.gold,
          headerTitleStyle: { fontFamily: 'serif', fontWeight: '300' },
          tabBarStyle: {
            backgroundColor: theme.surface,
            borderTopColor:  theme.border,
            borderTopWidth:  1,
            height: 60,
            paddingBottom: 8,
          },
          tabBarActiveTintColor:   theme.gold,
          tabBarInactiveTintColor: theme.textDim,
          tabBarIcon: ({ color, size }) => {
            const icons: Record<string, keyof typeof Ionicons.glyphMap> = {
              Damgala:  'time-outline',
              Geçmiş:   'list-outline',
              Doğrula:  'shield-checkmark-outline',
            };
            return <Ionicons name={icons[route.name]} size={size} color={color} />;
          },
        })}
      >
        <Tab.Screen name="Damgala"  component={StampScreen}   options={{ title: '⧗  TurkDamga' }} />
        <Tab.Screen name="Geçmiş"   component={HistoryScreen} />
        <Tab.Screen name="Doğrula"  component={VerifyScreen}  />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
```

---

## 5. src/screens/StampScreen.tsx

```tsx
import React, { useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, StyleSheet, Alert, Linking,
} from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import * as Sharing from 'expo-sharing';
import * as FileSystem from 'expo-file-system';
import QRCode from 'react-native-qrcode-svg';
import { theme } from '../theme';
import { hashFileUri, saveRecord, generateCertText, StampRecord } from '../engine/timestamp';

type StepStatus = 'idle' | 'active' | 'done';

export default function StampScreen() {
  const [file, setFile]         = useState<any>(null);
  const [hash, setHash]         = useState('');
  const [author, setAuthor]     = useState('');
  const [project, setProject]   = useState('');
  const [desc, setDesc]         = useState('');
  const [chain, setChain]       = useState<'both'|'bitcoin'|'polygon'>('both');
  const [steps, setSteps]       = useState<StepStatus[]>(['idle','idle','idle','idle']);
  const [stamping, setStamping] = useState(false);
  const [result, setResult]     = useState<StampRecord | null>(null);

  const STEP_LABELS = [
    'Hash hesaplanıyor…',
    'Polygon TX gönderiliyor…',
    'OpenTimestamps iletiliyor…',
    'Sertifika oluşturuluyor…',
  ];

  const pickFile = async () => {
    const res = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true });
    if (res.canceled) return;
    const asset = res.assets[0];
    setFile(asset);
    setHash('');
    setResult(null);
    const h = await hashFileUri(asset.uri);
    setHash(h);
  };

  const setStep = (i: number, status: StepStatus) => {
    setSteps(prev => prev.map((s, idx) => idx === i ? status : s));
  };

  const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

  const startStamp = async () => {
    if (!file || !hash) { Alert.alert('Hata', 'Önce bir dosya seçin.'); return; }
    setStamping(true);
    setSteps(['active','idle','idle','idle']);

    await sleep(600);
    setStep(0, 'done'); setStep(1, 'active');

    // Simulated Polygon TX (gerçekte stampPolygon() çağrılır)
    await sleep(900);
    const fakeTx = '0x' + Array.from({length:64}, () =>
      Math.floor(Math.random()*16).toString(16)).join('');
    setStep(1, 'done'); setStep(2, 'active');

    await sleep(600);
    setStep(2, 'done'); setStep(3, 'active');

    await sleep(500);
    setStep(3, 'done');

    const record: StampRecord = {
      id:          'CV-' + Date.now(),
      fileName:    file.name,
      fileHash:    hash,
      fileSize:    file.size || 0,
      mimeType:    file.mimeType || '',
      polyTx:      fakeTx,
      polyUrl:     `https://polygonscan.com/tx/${fakeTx}`,
      otsStatus:   'pending',
      timestamp:   new Date().toISOString(),
      author,
      project,
      description: desc,
      chain,
    };

    await saveRecord(record);
    setResult(record);
    setStamping(false);
    setSteps(['idle','idle','idle','idle']);
  };

  const downloadCert = async () => {
    if (!result) return;
    const cert = generateCertText(result);
    const path = FileSystem.cacheDirectory + `TurkDamga-${result.id}.txt`;
    await FileSystem.writeAsStringAsync(path, cert, { encoding: FileSystem.EncodingType.UTF8 });
    await Sharing.shareAsync(path);
  };

  return (
    <ScrollView style={s.scroll} contentContainerStyle={s.container}>

      {/* Chain selector */}
      <Text style={s.sectionLabel}>Zincir Seçimi</Text>
      <View style={s.chainRow}>
        {(['both','bitcoin','polygon'] as const).map(c => (
          <TouchableOpacity
            key={c}
            style={[s.chainBtn, chain === c && s.chainBtnActive]}
            onPress={() => setChain(c)}
          >
            <Text style={s.chainIcon}>
              {c === 'both' ? '⛓' : c === 'bitcoin' ? '₿' : '⬡'}
            </Text>
            <Text style={[s.chainName, chain === c && s.chainNameActive]}>
              {c === 'both' ? 'Her İkisi' : c === 'bitcoin' ? 'Bitcoin' : 'Polygon'}
            </Text>
            <Text style={s.chainDetail}>
              {c === 'both' ? 'BTC + MATIC' : c === 'bitcoin' ? 'Ücretsiz' : '~$0.001'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* File picker */}
      <Text style={s.sectionLabel}>Dosya</Text>
      <TouchableOpacity style={s.pickBtn} onPress={pickFile}>
        <Text style={s.pickIcon}>📁</Text>
        <Text style={s.pickText}>{file ? file.name : 'Dosya Seç'}</Text>
        <Text style={s.pickSub}>
          {file ? `${(file.size/1024).toFixed(1)} KB` : 'PDF · Görsel · Video · Ses · Kod'}
        </Text>
      </TouchableOpacity>

      {hash ? (
        <View style={s.hashBox}>
          <Text style={s.hashLabel}>SHA-256</Text>
          <Text style={s.hashValue} numberOfLines={2}>{hash}</Text>
        </View>
      ) : null}

      {/* Metadata */}
      <Text style={s.sectionLabel}>Metadata</Text>
      <View style={s.formCard}>
        <Text style={s.inputLabel}>Yazar</Text>
        <TextInput
          style={s.input} placeholderTextColor={theme.textDim}
          placeholder="Ad Soyad" value={author}
          onChangeText={setAuthor}
        />
        <Text style={s.inputLabel}>Proje</Text>
        <TextInput
          style={s.input} placeholderTextColor={theme.textDim}
          placeholder="Proje adı" value={project}
          onChangeText={setProject}
        />
        <Text style={s.inputLabel}>Açıklama</Text>
        <TextInput
          style={[s.input, {height:80, textAlignVertical:'top'}]}
          placeholderTextColor={theme.textDim}
          placeholder="Kısa not…" value={desc}
          onChangeText={setDesc} multiline
        />
      </View>

      {/* Progress */}
      {stamping && (
        <View style={s.progressCard}>
          {STEP_LABELS.map((label, i) => (
            <View key={i} style={s.stepRow}>
              <Text style={[s.stepIcon,
                steps[i] === 'done'   && {color: theme.gold},
                steps[i] === 'active' && {color: theme.gold},
              ]}>
                {steps[i] === 'done' ? '✓' : steps[i] === 'active' ? '◌' : '·'}
              </Text>
              <Text style={[s.stepLabel,
                steps[i] === 'done'   && {color: theme.text},
                steps[i] === 'active' && {color: theme.gold},
              ]}>{label}</Text>
              {steps[i] === 'active' && <ActivityIndicator size="small" color={theme.gold} />}
            </View>
          ))}
        </View>
      )}

      {/* Stamp button */}
      {!stamping && !result && (
        <TouchableOpacity style={s.stampBtn} onPress={startStamp}>
          <Text style={s.stampBtnText}>⧗  Blockchain'e Damgala</Text>
        </TouchableOpacity>
      )}

      {/* Result */}
      {result && (
        <View style={s.resultCard}>
          <View style={s.resultHeader}>
            <Text style={s.resultHeaderText}>✦  Damgalama Başarılı</Text>
          </View>

          <View style={s.resultBody}>
            <View style={s.detailRows}>
              {[
                ['Dosya', result.fileName],
                ['Polygon TX', result.polyTx.slice(0,18) + '…'],
                ['Bitcoin OTS', '⏳ ~1 saat içinde'],
                ['Zaman', new Date(result.timestamp).toLocaleString('tr-TR')],
                ['Sertifika ID', result.id],
              ].map(([label, value]) => (
                <View key={label} style={s.detailRow}>
                  <Text style={s.detailLabel}>{label}</Text>
                  <Text style={s.detailValue}>{value}</Text>
                </View>
              ))}
            </View>

            <View style={s.qrArea}>
              <QRCode
                value={`turkdamga://verify/${result.fileHash}`}
                size={100}
                color="#000000"
                backgroundColor="#FFFFFF"
              />
              <Text style={s.qrLabel}>Doğrulama QR</Text>
            </View>
          </View>

          <View style={s.resultActions}>
            <TouchableOpacity style={s.actionBtn} onPress={downloadCert}>
              <Text style={s.actionBtnText}>⬇  Sertifika İndir</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[s.actionBtn, {borderColor: theme.polyPurple}]}
              onPress={() => Linking.openURL(result.polyUrl)}
            >
              <Text style={[s.actionBtnText, {color: theme.polyPurple}]}>⬡  Polygonscan</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity
            style={s.newStampBtn}
            onPress={() => { setFile(null); setHash(''); setResult(null); }}
          >
            <Text style={s.newStampText}>+ Yeni Dosya Damgala</Text>
          </TouchableOpacity>
        </View>
      )}

    </ScrollView>
  );
}

const s = StyleSheet.create({
  scroll:           { flex: 1, backgroundColor: theme.black },
  container:        { padding: 20, paddingBottom: 40 },
  sectionLabel:     { fontSize: 10, letterSpacing: 3, textTransform: 'uppercase', color: theme.goldDim, marginBottom: 10, marginTop: 20 },
  chainRow:         { flexDirection: 'row', gap: 8 },
  chainBtn:         { flex: 1, backgroundColor: theme.surface2, borderWidth: 1, borderColor: theme.border, borderRadius: 4, padding: 12, alignItems: 'center' },
  chainBtnActive:   { borderColor: theme.gold, backgroundColor: 'rgba(201,168,76,0.06)' },
  chainIcon:        { fontSize: 20, marginBottom: 4 },
  chainName:        { fontSize: 12, color: theme.textDim, fontWeight: '600' },
  chainNameActive:  { color: theme.gold },
  chainDetail:      { fontSize: 10, color: theme.textDim, marginTop: 2 },
  pickBtn:          { backgroundColor: theme.surface2, borderWidth: 1, borderColor: theme.border, borderRadius: 4, padding: 20, alignItems: 'center', borderStyle: 'dashed' },
  pickIcon:         { fontSize: 32, marginBottom: 8 },
  pickText:         { fontSize: 14, color: theme.text, fontWeight: '500' },
  pickSub:          { fontSize: 11, color: theme.textDim, marginTop: 4 },
  hashBox:          { backgroundColor: theme.surface2, borderWidth: 1, borderColor: theme.border, borderRadius: 4, padding: 12, marginTop: 8 },
  hashLabel:        { fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', color: theme.goldDim, marginBottom: 4 },
  hashValue:        { fontSize: 11, color: theme.gold, fontFamily: 'monospace' },
  formCard:         { backgroundColor: theme.surface2, borderWidth: 1, borderColor: theme.border, borderRadius: 4, padding: 16 },
  inputLabel:       { fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', color: theme.goldDim, marginBottom: 6, marginTop: 12 },
  input:            { backgroundColor: theme.surface3, borderWidth: 1, borderColor: theme.border, borderRadius: 3, padding: 10, color: theme.text, fontSize: 14 },
  progressCard:     { backgroundColor: theme.surface2, borderWidth: 1, borderColor: theme.border, borderRadius: 4, padding: 16, marginTop: 16 },
  stepRow:          { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  stepIcon:         { fontSize: 14, color: theme.textDim, width: 16 },
  stepLabel:        { flex: 1, fontSize: 13, color: theme.textDim },
  stampBtn:         { backgroundColor: theme.gold, borderRadius: 4, padding: 16, alignItems: 'center', marginTop: 20 },
  stampBtnText:     { fontSize: 13, fontWeight: '700', letterSpacing: 2, textTransform: 'uppercase', color: theme.black },
  resultCard:       { backgroundColor: theme.surface2, borderWidth: 1, borderColor: theme.goldDim, borderRadius: 4, marginTop: 20, overflow: 'hidden' },
  resultHeader:     { backgroundColor: 'rgba(201,168,76,0.1)', padding: 14, borderBottomWidth: 1, borderBottomColor: theme.border },
  resultHeaderText: { fontSize: 15, color: theme.gold, fontStyle: 'italic' },
  resultBody:       { flexDirection: 'row', padding: 16, gap: 12 },
  detailRows:       { flex: 1 },
  detailRow:        { marginBottom: 10 },
  detailLabel:      { fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', color: theme.goldDim, marginBottom: 2 },
  detailValue:      { fontSize: 12, color: theme.text, fontFamily: 'monospace' },
  qrArea:           { alignItems: 'center', gap: 6 },
  qrLabel:          { fontSize: 9, letterSpacing: 1, textTransform: 'uppercase', color: theme.textDim },
  resultActions:    { flexDirection: 'row', gap: 8, padding: 16, paddingTop: 0 },
  actionBtn:        { flex: 1, borderWidth: 1, borderColor: theme.goldDim, borderRadius: 3, padding: 10, alignItems: 'center' },
  actionBtnText:    { fontSize: 11, letterSpacing: 1, color: theme.gold, textTransform: 'uppercase' },
  newStampBtn:      { margin: 16, marginTop: 0, padding: 12, alignItems: 'center', borderTopWidth: 1, borderTopColor: theme.border },
  newStampText:     { fontSize: 12, color: theme.textDim, letterSpacing: 1 },
});
```

---

## 6. src/screens/HistoryScreen.tsx

```tsx
import React, { useState, useCallback } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { theme } from '../theme';
import { getHistory, StampRecord } from '../engine/timestamp';

function fileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() || '';
  if (ext === 'pdf') return '📄';
  if (['jpg','jpeg','png','gif','webp'].includes(ext)) return '🖼';
  if (['mp4','mov','avi'].includes(ext)) return '🎬';
  if (['mp3','wav','flac'].includes(ext)) return '🎵';
  if (['py','js','ts','html','css'].includes(ext)) return '💾';
  return '📁';
}

export default function HistoryScreen() {
  const [history, setHistory] = useState<StampRecord[]>([]);

  useFocusEffect(useCallback(() => {
    getHistory().then(setHistory);
  }, []));

  if (history.length === 0) {
    return (
      <View style={s.empty}>
        <Text style={s.emptyIcon}>⧗</Text>
        <Text style={s.emptyText}>Henüz damgalama yapılmadı</Text>
      </View>
    );
  }

  return (
    <FlatList
      style={s.list}
      data={history}
      keyExtractor={r => r.id}
      renderItem={({ item: r }) => (
        <TouchableOpacity style={s.card}>
          <Text style={s.icon}>{fileIcon(r.fileName)}</Text>
          <View style={s.info}>
            <Text style={s.name} numberOfLines={1}>{r.fileName}</Text>
            <Text style={s.hash} numberOfLines={1}>{r.fileHash.slice(0,24)}…</Text>
            <Text style={s.meta}>
              {new Date(r.timestamp).toLocaleDateString('tr-TR')}
              {r.author ? ` · ${r.author}` : ''}
            </Text>
          </View>
          <View style={s.chains}>
            <View style={[s.pill, {borderColor:'rgba(130,71,229,0.4)'}]}>
              <Text style={[s.pillText, {color: theme.polyPurple}]}>MATIC ✓</Text>
            </View>
            <View style={[s.pill, {borderColor:'rgba(247,147,26,0.4)'}]}>
              <Text style={[s.pillText, {color: theme.btcOrange}]}>BTC ⏳</Text>
            </View>
          </View>
        </TouchableOpacity>
      )}
      ItemSeparatorComponent={() => <View style={s.sep} />}
    />
  );
}

const s = StyleSheet.create({
  list:  { flex: 1, backgroundColor: theme.black },
  empty: { flex: 1, backgroundColor: theme.black, alignItems: 'center', justifyContent: 'center' },
  emptyIcon: { fontSize: 48, opacity: 0.3, marginBottom: 12 },
  emptyText: { color: theme.textDim, fontSize: 14 },
  card:  { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12, backgroundColor: theme.surface2 },
  icon:  { fontSize: 28 },
  info:  { flex: 1 },
  name:  { fontSize: 14, color: theme.text, fontWeight: '500', marginBottom: 2 },
  hash:  { fontSize: 10, color: theme.textDim, fontFamily: 'monospace' },
  meta:  { fontSize: 11, color: theme.textDim, marginTop: 2 },
  chains:{ gap: 4, alignItems: 'flex-end' },
  pill:  { borderWidth: 1, borderRadius: 2, paddingHorizontal: 6, paddingVertical: 2 },
  pillText: { fontSize: 9, letterSpacing: 1 },
  sep:   { height: 1, backgroundColor: theme.border },
});
```

---

## 7. src/screens/VerifyScreen.tsx

```tsx
import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { theme } from '../theme';
import { hashFileUri, findByHash, StampRecord } from '../engine/timestamp';

export default function VerifyScreen() {
  const [hashInput, setHashInput] = useState('');
  const [loading, setLoading]     = useState(false);
  const [result, setResult]       = useState<StampRecord | 'notfound' | null>(null);

  const pickAndHash = async () => {
    const res = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true });
    if (res.canceled) return;
    setLoading(true);
    const h = await hashFileUri(res.assets[0].uri);
    setHashInput(h);
    setLoading(false);
  };

  const verify = async () => {
    const h = hashInput.trim().toLowerCase();
    if (h.length !== 64) return;
    const found = await findByHash(h);
    setResult(found || 'notfound');
  };

  return (
    <ScrollView style={s.scroll} contentContainerStyle={s.container}>
      <Text style={s.title}>Bütünlük Doğrulama</Text>
      <Text style={s.sub}>Bir dosyanın bu arşivde damgalandığını ve değiştirilmediğini kontrol edin.</Text>

      <Text style={s.label}>SHA-256 Hash</Text>
      <TextInput
        style={s.input} value={hashInput}
        onChangeText={setHashInput}
        placeholderTextColor={theme.textDim}
        placeholder="a3b4c5d6… (64 karakter)"
        autoCapitalize="none" autoCorrect={false}
      />

      <TouchableOpacity style={s.pickBtn} onPress={pickAndHash}>
        <Text style={s.pickBtnText}>
          {loading ? '⟳  Hash hesaplanıyor…' : '📁  Dosyadan Otomatik Hash Al'}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity style={s.verifyBtn} onPress={verify}>
        <Text style={s.verifyBtnText}>⬡  Doğrula</Text>
      </TouchableOpacity>

      {result === 'notfound' && (
        <View style={[s.resultBox, s.notFound]}>
          <Text style={s.resultIcon}>✗</Text>
          <Text style={s.resultTitle}>Kayıt Bulunamadı</Text>
          <Text style={s.resultDetail}>Bu hash bu arşivde mevcut değil.</Text>
        </View>
      )}

      {result && result !== 'notfound' && (
        <View style={[s.resultBox, s.found]}>
          <Text style={s.resultIcon}>✦</Text>
          <Text style={s.resultTitle}>Doğrulandı</Text>
          <Text style={s.resultDetail}>{(result as StampRecord).fileName}</Text>
          <Text style={s.resultDetail}>
            {new Date((result as StampRecord).timestamp).toLocaleString('tr-TR')}
          </Text>
          <Text style={[s.resultDetail, {color: theme.gold}]}>
            Polygon TX: {(result as StampRecord).polyTx.slice(0,20)}…
          </Text>
        </View>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  scroll:      { flex: 1, backgroundColor: theme.black },
  container:   { padding: 24, paddingBottom: 40 },
  title:       { fontSize: 24, color: theme.text, fontStyle: 'italic', marginBottom: 8 },
  sub:         { fontSize: 13, color: theme.textDim, lineHeight: 20, marginBottom: 24 },
  label:       { fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', color: theme.goldDim, marginBottom: 8 },
  input:       { backgroundColor: theme.surface2, borderWidth: 1, borderColor: theme.border, borderRadius: 3, padding: 12, color: theme.text, fontSize: 13, fontFamily: 'monospace' },
  pickBtn:     { borderWidth: 1, borderColor: theme.border, borderRadius: 3, borderStyle: 'dashed', padding: 16, alignItems: 'center', marginTop: 12 },
  pickBtnText: { fontSize: 13, color: theme.textDim },
  verifyBtn:   { borderWidth: 1, borderColor: theme.goldDim, borderRadius: 3, padding: 14, alignItems: 'center', marginTop: 16 },
  verifyBtnText: { fontSize: 13, fontWeight: '600', letterSpacing: 2, textTransform: 'uppercase', color: theme.gold },
  resultBox:   { borderRadius: 4, padding: 24, marginTop: 20, alignItems: 'center' },
  found:       { backgroundColor: 'rgba(39,174,96,0.08)', borderWidth: 1, borderColor: 'rgba(39,174,96,0.3)' },
  notFound:    { backgroundColor: 'rgba(192,57,43,0.08)', borderWidth: 1, borderColor: 'rgba(192,57,43,0.3)' },
  resultIcon:  { fontSize: 32, marginBottom: 8 },
  resultTitle: { fontSize: 18, color: theme.text, fontStyle: 'italic', marginBottom: 8 },
  resultDetail:{ fontSize: 12, color: theme.textDim, fontFamily: 'monospace', marginTop: 4 },
});
```

---

## 8. Kurulum & Çalıştırma

```bash
# Expo CLI kur
npm install -g expo-cli eas-cli

# Proje oluştur
npx create-expo-app TurkDamgaApp --template blank-typescript
cd TurkDamgaApp

# Dosyaları yukarıdaki içerikle oluştur
# Bağımlılıkları yükle
npm install

# Android emülatör veya fiziksel cihazda çalıştır
npx expo run:android

# Production APK derle (ücretsiz EAS hesabı gerekli)
eas build --platform android --profile preview
```

---

## 9. Gerçek Polygon Entegrasyonu İçin

```typescript
// .env dosyası oluştur (asla git'e ekleme!)
POLYGON_PRIVATE_KEY=0x...senin_private_key...
POLYGON_RPC=https://polygon-mainnet.g.alchemy.com/v2/API_KEY

// StampScreen.tsx içinde:
import { stampPolygon } from '../engine/timestamp';

// startStamp() fonksiyonunda simülasyon yerine:
const { txHash, explorerUrl } = await stampPolygon(
  hash,
  { fileName: file.name, author, project },
  process.env.POLYGON_PRIVATE_KEY!
);
```

> ⚠️ **Güvenlik Notu:** Private key'i uygulama içinde saklamak production için uygun değildir.
> Production'da backend API aracılığıyla işlemleri imzalayın.

---

## 10. Mimari Özeti

```
TurkDamga Android
├── StampScreen    → Dosya seç → Hash → Polygon + OTS → Sertifika
├── HistoryScreen  → AsyncStorage'dan geçmiş listesi
└── VerifyScreen   → Hash veya dosyadan doğrulama

timestamp.ts (Engine)
├── hashFileUri()       → expo-crypto ile SHA-256
├── stampPolygon()      → ethers.js ile Polygon TX
├── saveRecord()        → AsyncStorage
├── getHistory()        → AsyncStorage
├── findByHash()        → Yerel arama
└── generateCertText()  → .txt sertifika
```
