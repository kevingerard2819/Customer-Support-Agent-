"""Local, auto-saving desktop annotation window. Run with Python 3.11+ and Tk."""
import argparse
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from annotation_store import Store, INTENTS, ROUTES, REASONS


class App:
    PAGE_SIZE = 20

    def __init__(self, root, repo):
        self.root, self.repo = root, Path(repo)
        self.store = Store(self.repo/'annotations/batch-200.json', self.repo/'annotations/golden-progress.json')
        self.examples = list(self.store.examples.values())
        self.page = 0
        self.current = None
        self.loading = False
        self.timer = None
        root.title('Spotify labels - saves directly to your repo')
        root.geometry('1220x820')
        root.minsize(960, 650)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('Treeview', rowheight=25, font=('Segoe UI', 10))
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))
        top = ttk.Frame(root, padding=12)
        top.pack(fill='x')
        ttk.Label(top, text='Spotify support labelling', font=('Segoe UI',16,'bold')).pack(side='left')
        ttk.Button(top,text='Export backup...',command=self.export).pack(side='right',padx=4)
        ttk.Button(top,text='Restore backup...',command=self.restore).pack(side='right',padx=4)
        ttk.Button(top,text='Guidelines',command=self.guidelines).pack(side='right',padx=4)
        self.status = tk.StringVar()
        ttk.Label(root,textvariable=self.status,padding=(12,0)).pack(fill='x')
        ttk.Label(root,text='Select a row, then choose Intent and Route below. Changes save automatically. Notes are optional.',padding=(12,6)).pack(fill='x')
        columns=('number','message','intent','route','flag')
        self.table=ttk.Treeview(root,columns=columns,show='headings',height=9,selectmode='browse')
        for col,title,width in [('number','#',45),('message','Customer message',590),('intent','Intent',215),('route','Route',110),('flag','Review',80)]:
            self.table.heading(col,text=title)
            self.table.column(col,width=width,minwidth=40,stretch=col=='message')
        scroll=ttk.Scrollbar(root,orient='vertical',command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        self.table.pack(fill='x',padx=12)
        self.table.bind('<<TreeviewSelect>>',self.select)
        nav=ttk.Frame(root,padding=(12,6));nav.pack(fill='x')
        ttk.Button(nav,text='Previous 20',command=lambda:self.move(-1)).pack(side='left')
        ttk.Button(nav,text='Next 20',command=lambda:self.move(1)).pack(side='left',padx=5)
        ttk.Button(nav,text='Next unlabelled',command=self.next_unlabelled).pack(side='left')
        self.page_text=tk.StringVar();ttk.Label(nav,textvariable=self.page_text).pack(side='right')
        self.message=tk.Text(root,height=8,wrap='word',font=('Segoe UI',11),padx=12,pady=8,bg='#f3f6f8',relief='flat')
        self.message.pack(fill='both',expand=True,padx=12,pady=4)
        self.message.configure(state='disabled')
        edit=ttk.Frame(root,padding=12);edit.pack(fill='x')
        self.vars={}
        for col,(key,title,values,width) in enumerate([
            ('intent','Intent (required)',INTENTS,28),('route','Route (required)',ROUTES,16),
            ('reason','Reason (optional)',REASONS,30),('flag','Review (optional)',('Unsure','Discuss'),12)]):
            ttk.Label(edit,text=title).grid(row=0,column=col,sticky='w',padx=4)
            var=tk.StringVar(); self.vars[key]=var
            combo=ttk.Combobox(edit,textvariable=var,values=('',*values),state='readonly',width=width)
            combo.grid(row=1,column=col,padx=4,sticky='ew')
            combo.bind('<<ComboboxSelected>>',self.save)
        ttk.Label(edit,text='Notes (optional)').grid(row=2,column=0,sticky='w',pady=(8,0))
        self.notes=tk.Text(edit,height=3,wrap='word',font=('Segoe UI',10))
        self.notes.grid(row=3,column=0,columnspan=4,sticky='ew',padx=4)
        self.notes.bind('<KeyRelease>',self.schedule_save)
        ttk.Button(edit,text='Save now',command=self.save).grid(row=4,column=3,sticky='e',pady=5)
        ttk.Label(root,text=f'Saved file: {self.store.path}',padding=(12,0,12,8),font=('Segoe UI',8)).pack(fill='x')
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.bind('<Control-s>',self.save)
        self.render_page()

    def progress(self, message='Ready'):
        self.status.set(f'{message} | {self.store.complete()} / {len(self.examples)} intent/route pairs completed')

    def row_values(self, i, example):
        label=self.store.data['labels'].get(example['tweet_id'],{})
        return (i+1,example['message'].replace('\n',' '),label.get('intent',''),label.get('route',''),label.get('flag',''))

    def render_page(self, selected=None):
        self.loading=True
        self.table.delete(*self.table.get_children())
        start=self.page*self.PAGE_SIZE
        subset=self.examples[start:start+self.PAGE_SIZE]
        for i,example in enumerate(subset,start):
            self.table.insert('', 'end', iid=example['tweet_id'], values=self.row_values(i,example))
        self.page_text.set(f'Batch {self.page+1} of {(len(self.examples)+self.PAGE_SIZE-1)//self.PAGE_SIZE}')
        self.current=None
        self.loading=False
        self.progress('Saved progress loaded' if self.store.path.exists() else 'Ready - no new labels yet')
        if subset:
            self.table.selection_set(selected or subset[0]['tweet_id'])
            self.table.see(selected or subset[0]['tweet_id'])

    def select(self, event=None):
        if self.loading or not self.table.selection(): return
        tweet_id=self.table.selection()[0]
        if tweet_id==self.current: return
        if self.current and not self.save():
            self.table.selection_set(self.current)
            return
        self.current=tweet_id
        ex=self.store.examples[tweet_id]
        label=self.store.data['labels'].get(tweet_id,{})
        self.loading=True
        for key,var in self.vars.items(): var.set(label.get(key,''))
        self.notes.delete('1.0','end');self.notes.insert('1.0',label.get('notes',''))
        contents=f'CURRENT CUSTOMER MESSAGE (tweet {tweet_id})\n{ex["message"]}\n\nEARLIER CONTEXT\n'
        contents+='\n\n'.join(f'{x["role"].upper()}: {x["text"]}' for x in ex['context']) or 'No earlier messages available.'
        if any(ex['context_status'].values()):
            contents+='\n\nContext warning: '+', '.join(k for k,v in ex['context_status'].items() if v)
        self.message.configure(state='normal');self.message.delete('1.0','end');self.message.insert('1.0',contents);self.message.configure(state='disabled')
        self.loading=False

    def schedule_save(self,event=None):
        if self.timer: self.root.after_cancel(self.timer)
        self.status.set('Saving notes...')
        self.timer=self.root.after(400,self.save)

    def save(self,event=None):
        if self.timer: self.root.after_cancel(self.timer); self.timer=None
        if self.loading or not self.current: return True
        fields={key:var.get() for key,var in self.vars.items()}
        fields['notes']=self.notes.get('1.0','end-1c')
        existing=self.store.data['labels'].get(self.current,{})
        if all(existing.get(k,'')==v for k,v in fields.items()): return True
        try:
            self.store.update(self.current,**fields)
        except Exception as error:
            self.status.set('NOT SAVED - '+str(error))
            messagebox.showerror('Could not save',str(error),parent=self.root)
            return False
        i=next(i for i,x in enumerate(self.examples) if x['tweet_id']==self.current)
        self.table.item(self.current,values=self.row_values(i,self.examples[i]))
        self.progress('Saved '+datetime.now().strftime('%H:%M:%S'))
        return True

    def move(self,delta):
        if self.save():
            self.page=max(0,min((len(self.examples)-1)//self.PAGE_SIZE,self.page+delta))
            self.render_page()

    def next_unlabelled(self):
        if not self.save(): return
        for i,ex in enumerate(self.examples):
            label=self.store.data['labels'].get(ex['tweet_id'],{})
            if not (label.get('intent') and label.get('route')):
                self.page=i//self.PAGE_SIZE;self.render_page(ex['tweet_id']);return
        messagebox.showinfo('All pairs labelled','All 200 intent/route pairs are saved. Review flags and reply evaluation are separate.',parent=self.root)

    def export(self):
        if not self.save(): return
        destination=filedialog.asksaveasfilename(parent=self.root,title='Export labels backup',defaultextension='.json',initialfile='spotify-labels-backup.json',filetypes=[('JSON labels','*.json')])
        if destination:
            try: self.store.export(destination);self.progress('Backup exported')
            except Exception as error: messagebox.showerror('Export failed',str(error),parent=self.root)

    def restore(self):
        if not self.save(): return
        source=filedialog.askopenfilename(parent=self.root,title='Restore labels backup',filetypes=[('JSON labels','*.json')])
        if source and messagebox.askyesno('Restore backup','Replace current progress with this backup? The previous version is kept as a .bak file.',parent=self.root):
            try: self.store.restore(source);self.render_page()
            except Exception as error: messagebox.showerror('Restore failed',str(error),parent=self.root)

    def guidelines(self):
        window=tk.Toplevel(self.root);window.title('Guidelines v0.2');window.geometry('760x740')
        view=tk.Text(window,wrap='word',font=('Segoe UI',11),padx=14,pady=14)
        scroll=ttk.Scrollbar(window,command=view.yview);view.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');view.pack(fill='both',expand=True)
        view.insert('1.0',(self.repo/'docs/annotation-guide.md').read_text(encoding='utf-8'));view.configure(state='disabled')

    def close(self):
        if self.save(): self.root.destroy()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    window=tk.Tk()
    try:
        App(window,args.repo)
        window.mainloop()
    except Exception as error:
        messagebox.showerror('Unable to open label batch',str(error),parent=window)
        raise
