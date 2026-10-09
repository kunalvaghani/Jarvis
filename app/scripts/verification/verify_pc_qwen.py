"""Fresh read-only PC resolver generations; never opens or modifies a user file."""
from jarvis.paths import APP_ROOT, artifact_path
import argparse,json,os
from pathlib import Path
from datetime import datetime,timezone
from jarvis.pc_context import context,prompt,SYSTEM,resolve_entries,canonical_resolution,validate_resolution
from scripts.training.train_qwen_weights import BASE,dump


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',type=Path,required=True);args=parser.parse_args()
    checkpoint=(BASE/args.checkpoint).resolve()
    if not checkpoint.is_relative_to(BASE/'artifacts'):parser.error('Use local artifacts')
    out=artifact_path(BASE, 'qwen-pc-live-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir()
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_TF='0',USE_FLAX='0')
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import PeftModel
    torch.set_num_threads(8)
    tokenizer=AutoTokenizer.from_pretrained(checkpoint,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(BASE/'models/qwen-jarvis-base',torch_dtype=torch.bfloat16,local_files_only=True).to('cuda')
    model=PeftModel.from_pretrained(model,checkpoint,local_files_only=True).eval()
    goals=['open project '+name for name in ['FinanceAgent','ColdEmail_Helper','Jarvis','MyOwnCli','MyPortfolioDesktop','Linkedout','General-Agent-Runtime','ai-reel-autopilot','AlienGuy_Game','Local-AI-System-Lab']]
    goals+=['open downloads folder','open documents folder','open project MissingJarvisTestProject']
    rows=[]
    for goal in goals:
        pc=context(BASE,goal);entries=pc['entries'];expected=resolve_entries(goal,entries)
        text=tokenizer.apply_chat_template([{'role':'system','content':SYSTEM},{'role':'user','content':prompt(goal,entries)}],tokenize=False,add_generation_prompt=True)
        tokens=tokenizer(text,return_tensors='pt').to('cuda')
        with torch.no_grad():result=model.generate(**tokens,do_sample=False,max_new_tokens=300,pad_token_id=tokenizer.eos_token_id)
        raw=tokenizer.decode(result[0,tokens.input_ids.shape[1]:],skip_special_tokens=True)
        try:actual=json.loads(raw);validate_resolution(actual,goal,entries);passed=True;error=None
        except ValueError as exc:passed=False;actual=None;error=str(exc)
        rows.append({'goal':goal,'expected':expected,'actual':actual,'passed':passed,'error':error,'raw':raw})
        dump(out/'results.json',{'method':'fresh trained-weight generation on live PC metadata; read-only, no app launch','rows':rows,'passed':sum(r['passed'] for r in rows),'total':len(rows)})
        print(json.dumps({'goal':goal,'passed':passed}),flush=True)
    print(str(out/'results.json'),flush=True)


if __name__=='__main__':main()
