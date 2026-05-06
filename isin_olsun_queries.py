import pyodbc
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

class IsinOlsunQueryEngine:
    def __init__(self, server="SVM-DWH01.KNSVM.DC", database="BlueCollarDB"):
        self.server = server
        self.database = database

    def get_connection(self):
        drivers = ['{ODBC Driver 18 for SQL Server}', '{ODBC Driver 17 for SQL Server}', '{SQL Server}']
        for driver in drivers:
            try:
                conn_str = f"Driver={driver};Server={self.server};Database={self.database};Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
                return pyodbc.connect(conn_str, timeout=30)
            except:
                continue
        return None

    def calculate_dates(self, target_date=None):
        if target_date:
            dt = datetime.strptime(target_date, "%Y-%m-%d")
        else:
            now = datetime.now()
            dt = now.replace(day=1) - timedelta(days=1)
        
        last_day = dt.replace(day=1) + timedelta(days=32)
        last_day = last_day.replace(day=1) - timedelta(days=1)
        first_day = dt.replace(day=1)
        next_month_start = (last_day + timedelta(days=1)).replace(day=1)
        
        return {
            "yyyymm": dt.strftime("%Y%m"),
            "first_day_hyphen": first_day.strftime("%Y-%m-%d"),
            "next_month_hyphen": next_month_start.strftime("%Y-%m-%d")
        }

    def _execute_query(self, sql):
        conn = self.get_connection()
        if not conn: return pd.DataFrame()
        try:
            return pd.read_sql(sql, conn)
        finally:
            conn.close()

    def run_aday_queries(self, dates):
        queries = {
            "main": f"""
                SET NOCOUNT ON;
                drop table if exists #emailizinli;
                select address as Email, case when account_type = N'Individual' then 2 else 1 end AccountType, permission into #emailizinli from (	
                    Select address,account_type,permission ,ROW_NUMBER() over(partition by address order by date desc) as sira
                    from Iys.dbo.IYSPermissionLog where brand = N'IO' and log_type = N'email'
                ) as a where sira =1;
                drop table if exists #smsizinli;
                select right(address,10) username,permission into #smsizinli from (	
                    Select address,permission, ROW_NUMBER() over(partition by address order by date desc) as sira
                    from Iys.dbo.IYSPermissionLog where brand = N'IO' and log_type = N'sms'
                ) as a where sira =1;
                drop table if exists #Pushizinli;
                select * into #Pushizinli from (
                    select a.Accountid, ROW_NUMBER() over(partition by a.accountid order by a.CreationDate desc) sira
                    from AccountConfirmation A where AccountConfirmationTypeId = 5
                ) a where sira =1;
                select 
                count(distinct case when right(a.Username,10) = s.username and a.AccountTypeId=2 and s.permission = 1 then a.AccountId end) as [SMS_İzinliAday],
                count(distinct case when a.Email=e.Email and a.AccountTypeId=2 and e.permission =1 then  a.AccountId end) as [EMAIL_İzinliAday],
                count(distinct case when  isnull(a.Email,'')<>'' and a.AccountTypeId=2 then a.AccountId end) as [EMAIL_DoluOlanAday],
                count(distinct case when a.Accountid=p.Accountid and a.AccountTypeId=2  then  a.AccountId end) as [PUSH_İzinliAday],
                COUNT(distinct case when c.IsIdentityNumberVerified = 1 then c.CandidateId end) as [TCKN_OnaylıAday]
                from Candidate c with (nolock)
                left join Account a with (nolock) on c.AccountId = a.AccountId
                left join #smsizinli s on right(a.Username,10) = s.username
                left join #emailizinli e on a.Email=e.Email
                left join #Pushizinli p on c.AccountId = p.AccountId
                where c.IsDeleted = 0 and a.IsDeleted =0 and a.AccountTypeId=2 and a.CreationDate < '{dates['next_month_hyphen']}'
            """,
            "exp": f"select count(*) as IsTecrubesiDolu from (select CandidateId, ROW_NUMBER() over(partition by CandidateId order by c.CreationDate desc) sira from CandidateWorkingExperience c with (nolock) where c.CreationDate < '{dates['next_month_hyphen']}') as a where sira = 1",
            "follow": f"SELECT count(DISTINCT CandidateId) as SirketTakipEden FROM OPENQUERY(POSTGRES,'select \"CandidateId\" from public.\"CandidateFollowing\" WHERE to_char(\"CreationDate\", ''YYYYMM'')=''{dates['yyyymm']}''')",
            "app": f"select COUNT(distinct CandidateId) as BasvuranAday from Elastic_ApplicationList with (nolock) where creationdate >= '{dates['first_day_hyphen']}' and creationdate < '{dates['next_month_hyphen']}'",
            "addr": f"select COUNT(*) as AdresDolu from Candidate with (nolock) where address is not null and creationdate < '{dates['next_month_hyphen']}'",
            "city": f"select COUNT(*) as SehirDolu from Candidate with (nolock) where CityName is not null and creationdate < '{dates['next_month_hyphen']}'",
            "comp_comp": f"SELECT count(DISTINCT CandidateId) as SirketSikayetEden FROM OPENQUERY(POSTGRES,'select \"CandidateId\" from public.\"CompanyComplaintFeedback\" WHERE to_char(\"CreationDate\", ''YYYYMM'')=''{dates['yyyymm']}''')",
            "job_comp": f"select count(distinct candidateID) as IlanSikayetEden from JobComplaintFeedback with (nolock) where CreationDate >= '{dates['first_day_hyphen']}' and CreationDate < '{dates['next_month_hyphen']}'",
            "review": f"SELECT count(DISTINCT CandidateId) as PuanlayanAday FROM OPENQUERY(POSTGRES,'select \"CandidateId\" from public.\"CompanyEvaluation\" WHERE to_char(\"CreationDate\", ''YYYYMM'')=''{dates['yyyymm']}''')"
        }
        
        results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_key = {executor.submit(self._execute_query, sql): key for key, sql in queries.items()}
            for future in future_to_key:
                df = future.result()
                if not df.empty:
                    for col in df.columns:
                        results[col] = int(df[col].iloc[0])
        return results

    def run_firma_queries(self, dates):
        queries = {
            "main": f"""
                SET NOCOUNT ON;
                drop table if exists #emailizinli;
                select address as Email, case when account_type = N'Individual' then 2 else 1 end AccountType, permission into #emailizinli from (	
                    Select address,account_type,permission ,ROW_NUMBER() over(partition by address order by date desc) as sira
                    from Iys.dbo.IYSPermissionLog where brand = N'IO' and log_type = N'email'
                ) as a where sira =1;
                drop table if exists #smsizinli;
                select right(address,10) username,permission into #smsizinli from (	
                    Select address,permission, ROW_NUMBER() over(partition by address order by date desc) as sira
                    from Iys.dbo.IYSPermissionLog where brand = N'IO' and log_type = N'sms'
                ) as a where sira =1;
                drop table if exists #Pushizinli;
                select * into #Pushizinli from (
                    select a.Accountid, ROW_NUMBER() over(partition by a.accountid order by a.CreationDate desc) sira
                    from AccountConfirmation A where AccountConfirmationTypeId = 5
                ) a where sira =1;
                select 
                count(distinct case when right(a.Username,10) = s.username and a.AccountTypeId=1 and s.permission = 1 then a.AccountId end) as [SMS_İzinliFirma],
                count(distinct case when a.Email=e.Email and a.AccountTypeId=1 and e.permission =1 then  a.AccountId end) as [EMAIL_İzinliFirma],
                count(distinct case when  isnull(a.Email,'')<>'' and a.AccountTypeId=1 then a.AccountId end) as [EMAIL_DoluOlanFirma],
                count(distinct case when a.Accountid=p.Accountid and a.AccountTypeId=1  then  a.AccountId end) as [PUSH_İzinliFirma],
                COUNT(distinct case when c.IsIdentityNumberVerified = 1 then c.CompanyId end) as [TCKN_OnaylıFirma],
                COUNT(distinct case when TaxNumber is not null then c.CompanyId end) as [VKKN_OnaylıFirma]
                from Company c left join Account a on c.AccountId = a.AccountId
                left join #smsizinli s on right(a.Username,10) = s.username
                left join #emailizinli e on a.Email=e.Email
                left join #Pushizinli p on c.AccountId = p.AccountId
                where c.IsDeleted = 0 and a.IsDeleted =0 and a.AccountTypeId=1 and a.CreationDate < '{dates['next_month_hyphen']}'
            """,
            "evrak_total": f"select COUNT(distinct CompanyId) as EvrakOnayliFirmaTotal from Company where CreationDate < '{dates['next_month_hyphen']}' and CompanyDocumentProcessType = 4",
            "rozet_total": f"select COUNT(distinct CV.CompanyId) as OnayliIsverenRozeti from CompanyVerification CV inner join Company c on CV.CompanyId = c.CompanyId where cv.IsDeleted = 0 and ActualEndDate is null and ProcessType <>3 and CompanyVerificationStateId in ('6','7') and c.CreationDate < '{dates['next_month_hyphen']}'",
            "rozet_monthly": f"select count(distinct cv.companyid) as RozetHakKazananMonthly from CompanyVerification cv inner join Company c on CV.CompanyId = c.CompanyId where CompanyVerificationStateId in (6,7) and c.CreationDate >= '{dates['first_day_hyphen']}' and c.CreationDate < '{dates['next_month_hyphen']}'",
            "rozet_hak_total": f"select COUNT(distinct CV.CompanyId) as ToplamRozetHakKazanan from CompanyVerification CV inner join Company c on CV.CompanyId = c.CompanyId where cv.IsDeleted = 0 and ActualEndDate is null and ProcessType <>3 and CompanyVerificationStateId in ('6','7') and c.CreationDate < '{dates['next_month_hyphen']}'",
            "job_total": f"select COUNT(distinct CompanyID) as IlanYayinlayanFirmaTotal from Elastic_JobList where startDate >= '{dates['first_day_hyphen']}' and startDate < '{dates['next_month_hyphen']}'",
            "job_active": f"select COUNT(distinct CompanyID) as IlanYayinlayanFirmaActive from Elastic_JobList where startDate >= '{dates['first_day_hyphen']}' and startDate < '{dates['next_month_hyphen']}' and isDeleted = 0",
            "evrak_monthly": f"SELECT count(DISTINCT CompanyId) as EvrakOnaylayanMonthly FROM OPENQUERY(POSTGRES,'select * from public.\"CompanyDocument\" WHERE to_char(\"CreationDate\", ''YYYYMM'')=''{dates['yyyymm']}''') WHERE isdeleted = 0"
        }
        
        results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_key = {executor.submit(self._execute_query, sql): key for key, sql in queries.items()}
            for future in future_to_key:
                df = future.result()
                if not df.empty:
                    for col in df.columns:
                        results[col] = int(df[col].iloc[0])
        return results
