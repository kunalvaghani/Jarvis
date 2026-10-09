import { app, BrowserWindow, session } from 'electron';
import { fileURLToPath } from 'node:url';
app.whenReady().then(()=>{
 session.defaultSession.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false));
 const win=new BrowserWindow({width:1200,height:800,webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true}});
 win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
 win.webContents.on('will-navigate',event=>event.preventDefault());
 win.loadFile(fileURLToPath(new URL('../dist/index.html',import.meta.url)));
});
app.on('window-all-closed',()=>{if(process.platform!=='darwin')app.quit();});
