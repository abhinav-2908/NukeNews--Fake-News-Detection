"""Train reproducible classical candidates using supplied ISOT CSV files."""
from pathlib import Path
import json, time, hashlib, pickle
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score,precision_recall_fscore_support,confusion_matrix,roc_auc_score,brier_score_loss
import joblib
ROOT=Path(__file__).resolve().parents[1]; RAW=ROOT/'data/raw'; SEED=42

def locate(candidates):
 for name in candidates:
  p=RAW/name
  if p.exists():return p
 raise FileNotFoundError(f"Missing one of {candidates} in {RAW}. Download the ISOT Fake News Dataset and place its real/fake CSV files there.")
def load():
 true=pd.read_csv(locate(['True.csv','true.csv','real.csv'])); fake=pd.read_csv(locate(['Fake.csv','fake.csv']))
 def combine(df,label):
  title=df.get('title',pd.Series('',index=df.index)).fillna('').astype(str)
  body=df.get('text',pd.Series('',index=df.index)).fillna('').astype(str)
  return pd.DataFrame({'text':(title+'\n'+body).str.strip(),'label':label})
 df=pd.concat([combine(true,1),combine(fake,0)],ignore_index=True)
 df=df[df.text.str.len()>=3].drop_duplicates('text').reset_index(drop=True)
 if df.label.nunique()!=2:raise ValueError('Dataset must contain real and fake examples.')
 return df

def main():
 df=load(); trainval,test=train_test_split(df,test_size=.15,random_state=SEED,stratify=df.label); train,val=train_test_split(trainval,test_size=.1765,random_state=SEED,stratify=trainval.label)
 candidates={'tfidf_logistic':LogisticRegression(max_iter=1000,class_weight='balanced'),'tfidf_nb':MultinomialNB(),'tfidf_calibrated_svm':CalibratedClassifierCV(LinearSVC(class_weight='balanced'),cv=3)}
 results={}; trained={}
 for name,clf in candidates.items():
  pipe=Pipeline([('tfidf',TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=300000,sublinear_tf=True)),('clf',clf)])
  started=time.perf_counter(); pipe.fit(train.text,train.label); duration=time.perf_counter()-started
  started=time.perf_counter(); pred=pipe.predict(val.text); latency=(time.perf_counter()-started)/len(val)
  prob=pipe.predict_proba(val.text)[:,1]
  class_p,class_r,class_f,_=precision_recall_fscore_support(val.label,pred,labels=[0,1],zero_division=0)
  results[name]={'accuracy':accuracy_score(val.label,pred),'precision_fake':float(class_p[0]),'recall_fake':float(class_r[0]),'f1_fake':float(class_f[0]),'precision_real':float(class_p[1]),'recall_real':float(class_r[1]),'f1_real':float(class_f[1]),'macro_f1':float(precision_recall_fscore_support(val.label,pred,average='macro',zero_division=0)[2]),'confusion_matrix':confusion_matrix(val.label,pred,labels=[0,1]).tolist(),'roc_auc':roc_auc_score(val.label,prob),'brier_score':brier_score_loss(val.label,prob),'training_seconds':duration,'inference_ms_per_item':latency*1000,'model_size_bytes':len(pickle.dumps(pipe))}
  trained[name]=pipe
 # Select on validation macro-F1; test set is reserved and evaluated once afterward.
 selected=max(results,key=lambda x:results[x]['macro_f1'])
 pipe=trained[selected]; pred=pipe.predict(test.text); prob=pipe.predict_proba(test.text)[:,1]
 class_p,class_r,class_f,_=precision_recall_fscore_support(test.label,pred,labels=[0,1],zero_division=0)
 test_result={'accuracy':accuracy_score(test.label,pred),'precision_fake':float(class_p[0]),'recall_fake':float(class_r[0]),'f1_fake':float(class_f[0]),'precision_real':float(class_p[1]),'recall_real':float(class_r[1]),'f1_real':float(class_f[1]),'macro_f1':float(precision_recall_fscore_support(test.label,pred,average='macro',zero_division=0)[2]),'confusion_matrix':confusion_matrix(test.label,pred,labels=[0,1]).tolist(),'roc_auc':roc_auc_score(test.label,prob),'brier_score':brier_score_loss(test.label,prob)}
 # Refit chosen model with train+validation after model selection, preserving test isolation.
 pipe.fit(trainval.text,trainval.label); (ROOT/'models').mkdir(exist_ok=True); joblib.dump(pipe,ROOT/'models/selected.joblib')
 metrics={'status':'measured','dataset':'ISOT Fake News Dataset','seed':SEED,'dataset_rows_after_dedup':len(df),'train_rows':len(train),'validation_rows':len(val),'test_rows':len(test),'dataset_files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in RAW.glob('*.csv')},'class_counts':df.label.value_counts().to_dict(),'selection_metric':'validation macro-F1','selected_model':selected,'validation':results,'held_out_test':test_result,'model_version':'selected-v1'}
 (ROOT/'artifacts').mkdir(exist_ok=True); (ROOT/'artifacts/metrics.json').write_text(json.dumps(metrics,indent=2)); print(json.dumps({'selected':selected,'validation':results,'held_out_test':test_result},indent=2))
if __name__=='__main__':main()
