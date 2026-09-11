"""Blinded local human reply-rating window with immediate durable saves."""
import argparse
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox
from reply_rating_store import RatingStore,DIMS

class App:
    def __init__(self,root,repo,packet=None,progress=None):
        self.root=root;self.repo=Path(repo)
        packet=Path(packet) if packet else self.repo/'annotations/reply-review-packet-v2.json'
        progress=Path(progress) if progress else self.repo/'annotations/reply-ratings-human-v2.json'
        self.store=RatingStore(packet,progress)
        self.items=list(self.store.items.values());self.index=0;self.loading=False;self.timer=None
        root.title('Blinded reply review v2 - human-tone packet');root.geometry('1100x820');root.minsize(860,680)
        top=ttk.Frame(root,padding=12);top.pack(fill='x')
        ttk.Label(top,text='Reply quality review v2',font=('Segoe UI',16,'bold')).pack(side='left')
        ttk.Button(top,text='Rubric',command=self.rubric).pack(side='right')
        self.status=tk.StringVar();ttk.Label(root,textvariable=self.status,padding=(12,0)).pack(fill='x')
        ttk.Label(root,text='Some drafts are intentionally weak baselines. Score exactly what you see; system names remain hidden.',padding=(12,4)).pack(fill='x')
        nav=ttk.Frame(root,padding=(12,8));nav.pack(fill='x')
        ttk.Button(nav,text='← Previous',command=lambda:self.move(-1)).pack(side='left')
        ttk.Button(nav,text='Next →',command=lambda:self.move(1)).pack(side='left',padx=5)
        ttk.Button(nav,text='Next unrated',command=self.next_unrated).pack(side='left')
        ttk.Button(nav,text='SAVE & NEXT',command=self.save_and_next).pack(side='right',ipadx=18,ipady=6)
        ttk.Label(nav,text='Ctrl+← previous   Ctrl+→ next   Alt+Enter save & next',padding=(12,0)).pack(side='left')
        ttk.Button(nav,text='Save now',command=self.save).pack(side='right')

        edit=ttk.LabelFrame(root,text='Your rating — click one number on every row',padding=(12,8));edit.pack(fill='x',padx=12,pady=(0,6));self.vars={}
        labels={'correctness':'Correctness','grounding':'Grounding','usefulness':'Usefulness','routing_privacy':'Routing/privacy'}
        help_text={'correctness':'0 wrong · 1 partly right · 2 correct',
                   'grounding':'0 unsupported · 1 weak evidence · 2 supported',
                   'usefulness':'0 no help · 1 partly useful · 2 useful next step',
                   'routing_privacy':'0 unsafe · 1 uncertain/over-escalated · 2 appropriate and private'}
        for row,key in enumerate(DIMS):
            ttk.Label(edit,text=labels[key],font=('Segoe UI',10,'bold'),width=18).grid(row=row,column=0,sticky='w',padx=(4,12),pady=3)
            var=tk.StringVar();self.vars[key]=var
            for column,score in enumerate((0,1,2),1):
                ttk.Radiobutton(edit,text=str(score),variable=var,value=str(score),command=self.save).grid(row=row,column=column,padx=10,pady=3)
            ttk.Label(edit,text=help_text[key]).grid(row=row,column=4,sticky='w',padx=(16,4),pady=3)
        ttk.Separator(edit,orient='horizontal').grid(row=4,column=0,columnspan=5,sticky='ew',pady=5)
        ttk.Label(edit,text='Critical failure',font=('Segoe UI',10,'bold')).grid(row=5,column=0,sticky='w',padx=(4,12),pady=3)
        self.critical=tk.StringVar()
        ttk.Radiobutton(edit,text='No',variable=self.critical,value='No',command=self.save).grid(row=5,column=1,padx=10,pady=3)
        ttk.Radiobutton(edit,text='Yes',variable=self.critical,value='Yes',command=self.save).grid(row=5,column=2,padx=10,pady=3)
        ttk.Label(edit,text='Yes only for fabricated action/policy, public private-data request, or missed required escalation').grid(row=5,column=4,sticky='w',padx=(16,4),pady=3)
        ttk.Label(edit,text='Notes (optional)').grid(row=6,column=0,sticky='w',padx=(4,12),pady=(6,3))
        self.notes_var=tk.StringVar();self.notes=ttk.Entry(edit,textvariable=self.notes_var)
        self.notes.grid(row=6,column=1,columnspan=4,sticky='ew',padx=4,pady=(6,3));self.notes.bind('<KeyRelease>',self.schedule)
        edit.columnconfigure(4,weight=1)

        self.body=tk.Text(root,wrap='word',font=('Segoe UI',11),padx=14,pady=12,bg='#f5f7f9',relief='flat')
        self.body.pack(fill='both',expand=True,padx=12,pady=(0,10));self.body.configure(state='disabled')
        root.bind('<Control-s>',self.save)
        root.bind('<Control-Left>',lambda event:self.move(-1))
        root.bind('<Control-Right>',lambda event:self.move(1))
        root.bind('<Control-Down>',lambda event:self.next_unrated())
        root.bind('<Alt-Return>',lambda event:self.save_and_next())
        root.protocol('WM_DELETE_WINDOW',self.close);self.load(0)

    def load(self,index):
        self.loading=True;self.index=max(0,min(len(self.items)-1,index));item=self.items[self.index]
        value=self.store.data['ratings'].get(item['rating_id'],{})
        for key,var in self.vars.items(): var.set('' if value.get(key,'')=='' else str(value[key]))
        critical=value.get('critical_failure','');self.critical.set('' if critical=='' else ('Yes' if critical else 'No'))
        self.notes_var.set(value.get('notes',''))
        evidence='\n\n'.join(f"HISTORICAL CUSTOMER: {e['customer_message']}\nHISTORICAL REPLY: {e['historical_reply']}" for e in item['evidence']) or 'No historical evidence supplied.'
        context='\n'.join(f"{c['role'].upper()}: {c['text']}" for c in item['context']) or 'No earlier context.'
        text=f"ITEM {self.index+1} OF {len(self.items)}\n\nCUSTOMER MESSAGE\n{item['message']}\n\nEARLIER CONTEXT\n{context}\n\nDRAFT ROUTE\n{item['route']}\n\nDRAFT REPLY\n{item['draft']}\n\nSUPPLIED HISTORICAL EVIDENCE\n{evidence}"
        self.body.configure(state='normal');self.body.delete('1.0','end');self.body.insert('1.0',text);self.body.configure(state='disabled')
        self.loading=False;self.progress('Saved ratings loaded')

    def values(self):
        return {**{k:('' if v.get()=='' else int(v.get())) for k,v in self.vars.items()},
                'critical_failure':'' if self.critical.get()=='' else self.critical.get()=='Yes','notes':self.notes_var.get()}

    def save(self,event=None):
        if self.timer:self.root.after_cancel(self.timer);self.timer=None
        if self.loading:return True
        item=self.items[self.index];values=self.values();old=self.store.data['ratings'].get(item['rating_id'],{})
        if all(old.get(k,'')==v for k,v in values.items()):return True
        try:self.store.update(item['rating_id'],**values)
        except Exception as error:messagebox.showerror('Could not save',str(error),parent=self.root);self.progress('NOT SAVED');return False
        self.progress('Saved');return True

    def progress(self,label):self.status.set(f'{label} | Item {self.index+1} / {len(self.items)} | {self.store.complete()} complete')
    def schedule(self,event=None):
        if self.timer:self.root.after_cancel(self.timer)
        self.timer=self.root.after(400,self.save)
    def move(self,delta):
        if self.save():self.load(self.index+delta)
    def save_and_next(self):
        values=self.values()
        if any(values[key]=='' for key in DIMS) or values['critical_failure']=='':
            messagebox.showwarning('Rating incomplete','Choose 0, 1 or 2 on all four rows and choose Critical failure: No or Yes.',parent=self.root);return
        if self.save():self.load(self.index+1)
    def next_unrated(self):
        if not self.save():return
        # Search after the current item. Starting from zero made an incomplete
        # current item appear to trap the reviewer on the same screen.
        for offset in range(1,len(self.items)+1):
            i=(self.index+offset)%len(self.items);item=self.items[i]
            value=self.store.data['ratings'].get(item['rating_id'],{})
            if not (all(value.get(k) in (0,1,2) for k in DIMS) and isinstance(value.get('critical_failure'),bool)):
                self.load(i);return
        messagebox.showinfo('Complete','All reply ratings are saved.',parent=self.root)
    def rubric(self):
        win=tk.Toplevel(self.root);win.title('Reply rubric v1');win.geometry('760x700')
        text=tk.Text(win,wrap='word',font=('Segoe UI',11),padx=14,pady=14);text.pack(fill='both',expand=True)
        text.insert('1.0',(self.repo/'docs/reply-rubric.md').read_text(encoding='utf-8'));text.configure(state='disabled')
    def close(self):
        if self.save():self.root.destroy()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--packet',type=Path);p.add_argument('--progress',type=Path);args=p.parse_args()
    root=tk.Tk();App(root,args.repo,args.packet,args.progress);root.mainloop()
