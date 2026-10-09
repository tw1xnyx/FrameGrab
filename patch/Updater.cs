using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Win32;

public class FileEntry { public string path; public string sha256; public string[] oldHashes; public bool allowAbsent; }
public class PatchManifest { public int schema; public string version; public string minimumVersion; public string[] exeHashes; public FileEntry[] files; }
public class JournalEntry { public string path; public bool existed; public string hash; }
public class Journal { public string backup; public JournalEntry[] entries; public string phase; }
public class UpdaterForm : Form {
    readonly ProgressBar bar = new ProgressBar(); readonly Label status = new Label(); readonly Label percent = new Label();
    readonly Button close = new Button(); readonly Button copy = new Button(); string details=""; bool running=true;
    public UpdaterForm() {
        Text="FrameGrab Update";ClientSize=new Size(540,250);FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;StartPosition=FormStartPosition.CenterScreen;
        BackColor=Color.FromArgb(246,248,253);Font=new Font("Segoe UI",10);
        Controls.Add(new Label {Text="FrameGrab 8.2",Font=new Font("Segoe UI",20,FontStyle.Bold),Location=new Point(28,24),AutoSize=true});
        Controls.Add(new Label {Text="Premiere compatibility & incremental updates",Location=new Point(30,68),AutoSize=true,ForeColor=Color.DimGray});
        status.SetBounds(30,108,475,38);status.Text="Locating your existing FrameGrab installation…";Controls.Add(status);
        bar.SetBounds(30,151,430,20);bar.Minimum=0;bar.Maximum=100;Controls.Add(bar);
        percent.SetBounds(468,151,55,25);percent.Text="0%";Controls.Add(percent);
        copy.SetBounds(30,196,130,32);copy.Text="Copy details";copy.Visible=false;copy.Click+=(s,e)=>Clipboard.SetText(details);Controls.Add(copy);
        close.SetBounds(395,196,110,32);close.Text="Close";close.Enabled=false;close.Click+=(s,e)=>Close();Controls.Add(close);
        FormClosing+=(s,e)=>{if(running)e.Cancel=true;};Shown+=async(s,e)=>await Run();
    }
    void UpdateUI(int n,string text){if(IsDisposed)return;BeginInvoke((Action)(()=>{bar.Value=Math.Max(0,Math.Min(100,n));percent.Text=n+"%";status.Text=text;}));}
    async Task Run(){int code=0;try{await Task.Run(()=>PatchEngine.Apply(Program.Target,UpdateUI));UpdateUI(100,"Update complete. FrameGrab is ready.");details="FrameGrab 8.2.0 incremental update completed.";}
        catch(Exception e){code=1;details=e.ToString();PatchEngine.Log(details);UpdateUI(bar.Value,"Update could not complete. See details; rollback status is recorded in the log.");}
        Program.ExitCode=code;running=false;close.Enabled=true;copy.Visible=true;close.Focus();}
}
public static class Program {
    public static string Target; public static bool Silent; public static int ExitCode;
#if TESTING
    public static int FailAfter=-1; public static int CrashAfter=-1; public static bool NoRestart;
#endif
    [STAThread] public static int Main(string[] args){
        for(int i=0;i<args.Length;i++){
            if(args[i]=="--target"&&i+1<args.Length)Target=args[++i];
            else if(args[i]=="--silent")Silent=true;
#if TESTING
            else if(args[i]=="--fail-after"&&i+1<args.Length)FailAfter=int.Parse(args[++i]);
            else if(args[i]=="--no-restart")NoRestart=true;
            else if(args[i]=="--crash-after"&&i+1<args.Length)CrashAfter=int.Parse(args[++i]);
#endif
        }
        if(Silent){try{PatchEngine.Apply(Target,(n,s)=>{});return 0;}catch(Exception e){PatchEngine.Log(e.ToString());return 1;}}
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new UpdaterForm());return ExitCode;
    }
}
public static class PatchEngine {
    static readonly JavaScriptSerializer Json=new JavaScriptSerializer{MaxJsonLength=4*1024*1024};
    static string journalName=Path.Combine("resources",".framegrab-update-transaction.json");
    static string logFile=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),"FrameGrab","logs","updater.log");
    public static void Log(string s){try{Directory.CreateDirectory(Path.GetDirectoryName(logFile));File.AppendAllText(logFile,DateTime.UtcNow.ToString("o")+" "+s+Environment.NewLine);}catch{}}
    static byte[] Resource(string name){using(var s=Assembly.GetExecutingAssembly().GetManifestResourceStream(name)){if(s==null)throw new Exception("Updater resource missing: "+name);using(var b=new MemoryStream()){s.CopyTo(b);return b.ToArray();}}}
    static string Hash(byte[] data){using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(data)).Replace("-","").ToLowerInvariant();}
    static string FileHash(string path){using(var sha=SHA256.Create())using(var f=File.OpenRead(path))return BitConverter.ToString(sha.ComputeHash(f)).Replace("-","").ToLowerInvariant();}
    static bool Verify(byte[] data,byte[] signature){using(var rsa=new RSACryptoServiceProvider()){rsa.PersistKeyInCsp=false;rsa.FromXmlString(Encoding.UTF8.GetString(Resource("publisher.xml")));return rsa.VerifyData(data,CryptoConfig.MapNameToOID("SHA256"),signature);}}
    static PatchManifest ReadManifest(byte[] data,byte[] signature){if(!Verify(data,signature))throw new Exception("Publisher signature verification failed. No files changed.");var m=Json.Deserialize<PatchManifest>(Encoding.UTF8.GetString(data));if(m.schema!=1||m.files==null||m.files.Length==0||m.files.Length>100)throw new Exception("Invalid signed patch manifest");return m;}
    static string SafePath(string root,string relative){
        if(String.IsNullOrEmpty(relative)||Path.IsPathRooted(relative)||relative.Contains(":")||relative.Split('/','\\').Any(x=>x==".."||x=="."||x.Length==0))throw new Exception("Invalid patch path");
        string full=Path.GetFullPath(Path.Combine(root,relative.Replace('/',Path.DirectorySeparatorChar)));
        if(!full.StartsWith(Path.GetFullPath(root).TrimEnd('\\')+"\\",StringComparison.OrdinalIgnoreCase))throw new Exception("Patch path escaped installation");
        string check=full;while(!String.IsNullOrEmpty(check)&&check.Length>=root.Length){if((File.Exists(check)||Directory.Exists(check))&&(File.GetAttributes(check)&FileAttributes.ReparsePoint)!=0)throw new Exception("Symbolic links are not accepted in patched paths");check=Path.GetDirectoryName(check);}
        return full;
    }
    static bool IsInstallation(string p){return !String.IsNullOrEmpty(p)&&File.Exists(Path.Combine(p,"FrameGrab.exe"))&&File.Exists(Path.Combine(p,"resources","app.asar"));}
    static string Discover(){
        var found=new List<string>();
        foreach(var hive in new[]{RegistryHive.CurrentUser,RegistryHive.LocalMachine})foreach(var view in new[]{RegistryView.Registry64,RegistryView.Registry32}){
            using(var baseKey=RegistryKey.OpenBaseKey(hive,view))using(var uninstall=baseKey.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall")){
                if(uninstall==null)continue;
                foreach(var name in uninstall.GetSubKeyNames())using(var k=uninstall.OpenSubKey(name)){
                    if(k==null||!Convert.ToString(k.GetValue("DisplayName")).StartsWith("FrameGrab",StringComparison.OrdinalIgnoreCase))continue;
                    string dir=Convert.ToString(k.GetValue("InstallLocation"));
                    if(!IsInstallation(dir)){
                        string icon=Convert.ToString(k.GetValue("DisplayIcon"));var match=Regex.Match(icon,"^\\\"?(.+?\\.exe)\\\"?(?:,.*)?$",RegexOptions.IgnoreCase);
                        if(match.Success)dir=Path.GetDirectoryName(match.Groups[1].Value);
                    }
                    if(!IsInstallation(dir)){
                        var match=Regex.Match(Convert.ToString(k.GetValue("UninstallString")),"^\\\"([^\\\"]+\\.exe)\\\"",RegexOptions.IgnoreCase);
                        if(match.Success)dir=Path.GetDirectoryName(match.Groups[1].Value);
                    }
                    if(IsInstallation(dir))found.Add(Path.GetFullPath(dir));
                }
            }
        }
        found=found.Distinct(StringComparer.OrdinalIgnoreCase).ToList();
        if(found.Count==1)return found[0];
        if(found.Count>1)throw new Exception("More than one FrameGrab installation was found. Run this updater with --target and the intended installed directory.");
        throw new Exception("An existing FrameGrab installation was not found. This update does not install the full application.");
    }
    static List<Process> AppProcesses(string root){var list=new List<Process>();foreach(var p in Process.GetProcessesByName("FrameGrab")){try{if(String.Equals(p.MainModule.FileName,Path.Combine(root,"FrameGrab.exe"),StringComparison.OrdinalIgnoreCase))list.Add(p);else p.Dispose();}catch{p.Dispose();}}return list;}
    static void KillTree(Process p){try{if(p.HasExited)return;using(var k=Process.Start(new ProcessStartInfo("taskkill.exe","/PID "+p.Id+" /T /F"){UseShellExecute=false,CreateNoWindow=true})){if(k!=null)k.WaitForExit(8000);}}catch{}}
    static void StopApps(string root){
        var processes=AppProcesses(root);foreach(var p in processes){try{p.CloseMainWindow();}catch{}}
        foreach(var p in processes){try{if(!p.WaitForExit(8000))KillTree(p);}finally{p.Dispose();}}
        // The native watchdog normally removes the backend. Shut down orphan pythonw only inside this installation.
        foreach(var p in Process.GetProcessesByName("pythonw")){try{if(String.Equals(p.MainModule.FileName,Path.Combine(root,"resources","runtime","pythonw.exe"),StringComparison.OrdinalIgnoreCase))KillTree(p);}catch{}finally{p.Dispose();}}
    }
    static void AtomicWrite(string target,byte[] bytes){Directory.CreateDirectory(Path.GetDirectoryName(target));string tmp=target+".patch-"+Guid.NewGuid().ToString("N");try{using(var f=new FileStream(tmp,FileMode.CreateNew,FileAccess.Write,FileShare.None)){f.Write(bytes,0,bytes.Length);f.Flush(true);}if(File.Exists(target))File.Replace(tmp,target,null);else File.Move(tmp,target);}finally{if(File.Exists(tmp))File.Delete(tmp);}}
    static void SaveJournal(string root,Journal j){AtomicWrite(SafePath(root,journalName),Encoding.UTF8.GetBytes(Json.Serialize(j)));}
    static void Restore(string root,Journal j){
        if(!Regex.IsMatch(j.backup??"","^[a-zA-Z0-9_.-]+$"))throw new Exception("Invalid recovery backup path");
        string backup=SafePath(root,".framegrab-backups/"+j.backup);var signed=ReadManifest(File.ReadAllBytes(Path.Combine(backup,"manifest.json")),File.ReadAllBytes(Path.Combine(backup,"manifest.sig")));
        foreach(var e in j.entries.Reverse()){
            var allowed=signed.files.SingleOrDefault(x=>x.path==e.path);if(allowed==null)throw new Exception("Recovery path is not in signed manifest");
            string target=SafePath(root,e.path);
            if(e.existed){if(!allowed.oldHashes.Contains(e.hash)&&allowed.sha256!=e.hash)throw new Exception("Untrusted recovery hash");string from=SafePath(backup,"original/"+e.path);if(FileHash(from)!=e.hash)throw new Exception("Backup verification failed; original backup retained at "+backup);AtomicWrite(target,File.ReadAllBytes(from));}
            else {if(!allowed.allowAbsent)throw new Exception("Unexpected missing recovery file");if(File.Exists(target))File.Delete(target);}
        }
        j.phase="rolled-back";SaveJournal(root,j);Log("Rollback succeeded from "+backup);
    }
    static Process Launch(string root){return Process.Start(new ProcessStartInfo(Path.Combine(root,"FrameGrab.exe")){WorkingDirectory=root,UseShellExecute=false,CreateNoWindow=true});}
    static void LaunchAndVerify(string root){
        string qa=Environment.GetEnvironmentVariable("FRAMEGRAB_QA_DATA");
        string data=Environment.GetEnvironmentVariable("FRAMEGRAB_QA")=="1"&&!String.IsNullOrEmpty(qa)?qa:Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),"FrameGrab");
        string log=Path.Combine(data,"logs","framegrab.log");long offset=File.Exists(log)?new FileInfo(log).Length:0;
        using(var p=Launch(root)){
            if(p==null)throw new Exception("Updated application did not launch");
            for(int n=0;n<90;n++){Thread.Sleep(500);if(p.HasExited)throw new Exception("Updated application exited during startup");
                try{if(File.Exists(log)){using(var f=new FileStream(log,FileMode.Open,FileAccess.Read,FileShare.ReadWrite)){if(f.Length<offset)offset=0;f.Position=offset;using(var reader=new StreamReader(f)){if(reader.ReadToEnd().Contains("engine ready on loopback port"))return;}}}}catch(IOException){}
            }
            KillTree(p);throw new Exception("Updated media engine did not become ready; restoring prior files");
        }
    }
    public static void Apply(string explicitRoot,Action<int,string> progress){
        var manifestBytes=Resource("manifest.json");var signature=Resource("manifest.sig");var m=ReadManifest(manifestBytes,signature);
        string root=Path.GetFullPath(explicitRoot??Discover()).TrimEnd('\\');if(!IsInstallation(root))throw new Exception("Target is not an installed FrameGrab application");
        string mutexName="Local\\FrameGrabPatch-"+Hash(Encoding.UTF8.GetBytes(root.ToLowerInvariant()));
        using(var mutex=new Mutex(false,mutexName)){
            bool taken=false;try{try{taken=mutex.WaitOne(10000);}catch(AbandonedMutexException){taken=true;}if(!taken)throw new Exception("Another FrameGrab update is already running");
                progress(5,"Verifying signed update and installed version…");
                if(!m.exeHashes.Contains(FileHash(Path.Combine(root,"FrameGrab.exe"))))throw new Exception("This patch does not recognize the installed FrameGrab executable. No files changed.");
                string journalPath=SafePath(root,journalName);
                if(File.Exists(journalPath)){var previous=Json.Deserialize<Journal>(File.ReadAllText(journalPath));if(previous.phase=="applying"){StopApps(root);Restore(root,previous);}}
                var changed=new List<FileEntry>();
                foreach(var e in m.files){string path=SafePath(root,e.path);if(File.Exists(path)){string hash=FileHash(path);if(hash==e.sha256)continue;if(e.oldHashes==null||!e.oldHashes.Contains(hash))throw new Exception("Unexpected installed file version: "+e.path+". No files changed.");}else if(!e.allowAbsent)throw new Exception("Required installed file missing: "+e.path);changed.Add(e);}
                if(changed.Count==0){progress(100,"This update is already installed.");return;}
                var payload=new Dictionary<string,byte[]>();
                using(var zip=new ZipArchive(new MemoryStream(Resource("payload.zip")),ZipArchiveMode.Read)){
                    if(zip.Entries.Count!=m.files.Length)throw new Exception("Unexpected payload file count");
                    foreach(var e in m.files){var z=zip.GetEntry(e.path);if(z==null||z.Length>25*1024*1024)throw new Exception("Payload file missing or too large");using(var data=new MemoryStream()){using(var stream=z.Open())stream.CopyTo(data);var bytes=data.ToArray();if(Hash(bytes)!=e.sha256)throw new Exception("Payload hash mismatch: "+e.path);payload.Add(e.path,bytes);}}
                }
                // Verify write access before closing the user's app. Elevate only when installation ACLs require it.
                string check=Path.Combine(root,".framegrab-write-"+Guid.NewGuid().ToString("N"));
                try{File.WriteAllText(check,"");File.Delete(check);}catch(UnauthorizedAccessException){
                    if(Program.Silent)throw;
                    Process.Start(new ProcessStartInfo(Assembly.GetExecutingAssembly().Location,"--target \""+root+"\""){UseShellExecute=true,Verb="runas"});progress(100,"Continue in the elevated updater window.");return;
                }
                var j=new Journal{backup=m.version+"-"+DateTime.UtcNow.Ticks,phase="applying",entries=changed.Select(e=>{string p=SafePath(root,e.path);return new JournalEntry{path=e.path,existed=File.Exists(p),hash=File.Exists(p)?FileHash(p):null};}).ToArray()};
                string backup=SafePath(root,".framegrab-backups/"+j.backup);Directory.CreateDirectory(backup);
                File.WriteAllBytes(Path.Combine(backup,"manifest.json"),manifestBytes);File.WriteAllBytes(Path.Combine(backup,"manifest.sig"),signature);
                progress(15,"Closing FrameGrab and backing up affected files…");StopApps(root);
                try {
                foreach(var e in j.entries)if(e.existed){string to=SafePath(backup,"original/"+e.path);Directory.CreateDirectory(Path.GetDirectoryName(to));File.Copy(SafePath(root,e.path),to);if(FileHash(to)!=e.hash)throw new Exception("Backup hash verification failed");}
                SaveJournal(root,j);
                } catch { Launch(root); throw; }
                try{
                    for(int i=0;i<changed.Count;i++){
                        var e=changed[i];AtomicWrite(SafePath(root,e.path),payload[e.path]);if(FileHash(SafePath(root,e.path))!=e.sha256)throw new Exception("Installed file hash mismatch");
                        progress(25+(i+1)*55/changed.Count,"Updating application files…");
#if TESTING
                        if(Program.CrashAfter==i+1)Environment.Exit(71);
                        if(Program.FailAfter==i+1)throw new Exception("Injected test failure after file replacement");
#endif
                    }
                    progress(85,"Restarting FrameGrab and checking its media engine…");
#if TESTING
                    if(!Program.NoRestart)LaunchAndVerify(root);
#else
                    LaunchAndVerify(root);
#endif
                    j.phase="complete";SaveJournal(root,j);Log("Updated to "+m.version+" at "+root+"; backup retained at "+backup);progress(100,"Update complete. Your settings and history are preserved.");
                }catch(Exception original){StopApps(root);try{Restore(root,j);
#if TESTING
                    if(!Program.NoRestart)Launch(root);
#else
                    Launch(root);
#endif
                    throw new Exception("Update failed; original application files were restored. "+original.Message,original);
                }catch(Exception rollback){if(rollback.Message.StartsWith("Update failed; original"))throw;throw new Exception("Update failed and automatic recovery needs attention. Backup retained at "+backup+". "+rollback.Message,original);}}
            }finally{if(taken)mutex.ReleaseMutex();}
        }
    }
}
