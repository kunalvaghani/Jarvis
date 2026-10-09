"""Bounded project scaffolds and stages. No package hooks or arbitrary shell."""
import json
from pathlib import Path
import re
from .agent_context import scoped
from .development_knowledge import detect_stack

STAGES = ('understand', 'design', 'scaffold', 'components', 'styling', 'functionality', 'verify')
VERSIONS = {'react': '19.3.0', 'react-dom': '19.3.0', 'vite': '8.3.2', 'typescript': '7.0.2',
            '@types/react': '19.3.0', '@types/react-dom': '19.3.0', 'motion': '14.0.0',
            'next': '16.3.8', 'electron': '44.5.1', 'axe-core': '4.13.0', '@types/node': '26.6.4', '@electron/packager': '20.3.0'}

def requested(project, goal):
    stack = detect_stack(project, goal)
    return stack in {'vite', 'next', 'electron', 'expo', 'react'} and bool(re.search(
        r'\b(build|create|make|add|edit|fix|update|animate|implement|design|develop|change)\b', goal, re.I))

def batches(plan, size=3):
    steps = plan.get('files')
    dirs = plan.get('directories', [])
    if not isinstance(steps, list) or not isinstance(dirs, list) or not 1 <= len(steps) <= 24 or len(dirs) > 12:
        raise ValueError('Development plan allows 24 files, 12 directories and three files per batch.')
    from .coder import relative_parts
    seen = set()
    for name in dirs:
        relative_parts(name, directory=True)
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get('reason'), str):
            raise ValueError('Invalid development step.')
        name = step.get('path')
        relative_parts(name)
        if name.casefold() in seen:
            raise ValueError('Repeated development path.')
        seen.add(name.casefold())
    return [steps[i:i+size] for i in range(0, len(steps), size)]

def scaffold_files(stack):
    if stack not in {'vite', 'next', 'electron', 'expo'}:
        raise ValueError('Unsupported scaffold; retain the existing stack.')
    deps = {name: VERSIONS[name] for name in ('react', 'react-dom', 'motion')}
    dev = {name: VERSIONS[name] for name in ('typescript', '@types/react', '@types/react-dom', 'axe-core')}
    package = {'name': 'jarvis-project', 'version': '0.1.0', 'private': True, 'type': 'module',
               'scripts': {'typecheck': 'tsc --noEmit'}, 'dependencies': deps, 'devDependencies': dev}
    config = {'compilerOptions': {'target': 'ES2022', 'lib': ['ES2022', 'DOM', 'DOM.Iterable'],
        'jsx': 'react-jsx', 'module': 'ESNext', 'moduleResolution': 'bundler', 'strict': True,
        'skipLibCheck': True, 'noEmit': True, 'allowSyntheticDefaultImports': True}, 'include': ['src']}
    files = {}
    if stack == 'expo':
        # SDK-compatible versions are pinned together, never guessed from latest RN.
        package['dependencies'] = {'expo': '57.0.26', 'react': '19.2.3', 'react-native': '0.86.3',
                                   'react-native-web': '0.21.3', 'react-dom': '19.2.3', '@expo/metro-runtime': '57.0.16'}
        package['main'] = 'index.js'
        package['scripts'].update(start='expo start', build='expo export --platform web')
        files['index.js'] = "import { registerRootComponent } from 'expo';\nimport App from './src/App';\nregisterRootComponent(App);\n"
        files['app.json'] = json.dumps({'expo': {'name': 'Jarvis Project', 'slug': 'jarvis-project',
                                               'web': {'bundler': 'metro'}}}, indent=2)
        files['src/App.tsx'] = '''import { useState } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
export default function App() {
 const [count,setCount]=useState(0);
 return <View style={styles.page}><Text style={styles.heading}>Your workspace</Text>
 <Text>Replace this starter with the requested app.</Text>
 <Pressable accessibilityRole="button" onPress={()=>setCount(n=>n+1)} style={styles.button}>
 <Text style={{color:'white'}}>Completed {count}</Text></Pressable></View>;
}
const styles=StyleSheet.create({page:{flex:1,padding:32,backgroundColor:'#f4f7f5',justifyContent:'center'},heading:{fontSize:32,fontWeight:'700'},button:{padding:16,backgroundColor:'#0d6559',borderRadius:12,marginTop:20}});
'''
    elif stack == 'next':
        deps['next'] = VERSIONS['next']
        dev['@types/node'] = VERSIONS['@types/node']
        package['scripts'].update(dev='next dev --hostname 127.0.0.1', build='next build', start='next start --hostname 127.0.0.1')
        config['include'] = ['next-env.d.ts', 'src', '.next/types/**/*.ts', '.next/dev/types/**/*.ts']
        config['exclude'] = ['node_modules']
        config['compilerOptions'].update(allowJs=True,incremental=True,esModuleInterop=True,resolveJsonModule=True,isolatedModules=True,plugins=[{'name':'next'}])
        files['src/app/layout.tsx'] = "import type { ReactNode } from 'react';\nimport './globals.css';\nexport const metadata = {title: 'Jarvis workspace', description: 'Local project workspace'};\nexport default function Layout({children}:{children:ReactNode}) { return <html lang=\"en\"><body>{children}</body></html>; }\n"
        files['src/app/page.tsx'] = "export default function Page() { return <main><h1>Your workspace</h1><p>Implement the requested application here.</p></main>; }\n"
        files['src/app/globals.css'] = 'body { margin: 0; font-family: system-ui; color: #172526; background: #f4f7f5; } main { max-width: 70rem; margin: auto; padding: 2rem; }\n'
        files['next-env.d.ts'] = '/// <reference types="next" />\n/// <reference types="next/image-types/global" />\n'
    else:
        dev['vite'] = VERSIONS['vite']
        package['scripts'].update(dev='vite --host 127.0.0.1', build='tsc --noEmit && vite build', preview='vite preview --host 127.0.0.1')
        files['index.html'] = '<!doctype html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/><title>Jarvis workspace</title></head><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>\n'
        files['src/main.tsx'] = "import { createRoot } from 'react-dom/client';\nimport App from './App';\nimport './styles.css';\ncreateRoot(document.getElementById('root')!).render(<App/>);\n"
        files['src/App.tsx'] = 'export default function App() { return <main><h1>Your workspace</h1><p>Implement the requested application here.</p></main>; }\n'
        files['src/styles.css'] = 'body { margin: 0; font-family: system-ui; color: #172526; background: #f4f7f5; } main { max-width: 70rem; margin: auto; padding: 2rem; }\n'
        files['vite.config.ts'] = "import { defineConfig } from 'vite';\nexport default defineConfig({ base: './' });\n"
        if stack == 'electron':
            dev['electron'] = VERSIONS['electron']
            dev['@electron/packager'] = VERSIONS['@electron/packager']
            package['main'] = 'electron/main.js'
            package['scripts']['desktop'] = 'electron .'
            files['electron/main.js'] = '''import { app, BrowserWindow, session } from 'electron';
import { fileURLToPath } from 'node:url';
app.whenReady().then(()=>{
 session.defaultSession.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false));
 const win=new BrowserWindow({width:1200,height:800,webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true}});
 win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
 win.webContents.on('will-navigate',event=>event.preventDefault());
 win.loadFile(fileURLToPath(new URL('../dist/index.html',import.meta.url)));
});
app.on('window-all-closed',()=>{if(process.platform!=='darwin')app.quit();});
'''
    if stack != 'expo':
        files['src/styles.d.ts'] = "declare module '*.css';\n"
    files['package.json'] = json.dumps(package, indent=2) + '\n'
    files['tsconfig.json'] = json.dumps(config, indent=2) + '\n'
    files['README.md'] = '# Jarvis project\n\nStarter only until implementation and verification pass.\n\nUse the Jarvis development workflow to install approved dependencies, type-check, build and inspect the owned preview. Native packaging requires its platform toolchain.\n'
    return files

def scaffold(project, stack, cancelled, report, checkpoint):
    project = Path(project).resolve(strict=True)
    if scoped(project, 'package.json').exists():
        return []
    files = scaffold_files(stack)
    # An empty source folder is allowed; pre-existing user files are never replaced.
    for name in files:
        if scoped(project, name).exists():
            raise ValueError('Scaffold would replace an existing file: ' + name)
    written = []
    for i, (name, content) in enumerate(files.items()):
        if cancelled():
            raise ValueError('Scaffold cancelled; inspect the recorded files before resuming.')
        path = scoped(project, name)
        checkpoint('development_scaffold', target=path, evidence=f'Batch {i//3+1}; new file only')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8', newline='') as out:
            out.write(content)
        if path.read_text(encoding='utf-8') != content:
            raise ValueError('Scaffold readback failed: ' + name)
        from .progress import status
        status(report, 'Scaffolding ' + stack, path, file=str(path), preview=content[:1600], characters=len(content), outcome='Starter saved; functionality pending')
        written.append(name)
        checkpoint('observed_file', target=path, evidence='Scaffold read back')
    return written
