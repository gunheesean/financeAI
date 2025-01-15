import requests
from bs4 import BeautifulSoup
import pandas as pd
from openai import OpenAI
import streamlit as st
import os

# OpenAI initialization
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Function to translate Korean company name to English
def translate_name_to_english(korean_name):
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an assistant that specializes in understanding company names. When provided with a Korean company name, identify and correct possible typos, then translate it to the most relevant English company name. Focus on finding the correct US company name."
            },
            {
                "role": "user",
                "content": f"The company name is: {korean_name}. Please correct typos if any and translate it. I just need the company name without explanations."
            }
        ],
        max_tokens=50,
        temperature=0.7
    )
    return completion.choices[0].message.content.strip()

# Function to get CIK from company name
def get_cik(company_name):
    english_name = translate_name_to_english(company_name)

    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {"User-Agent": "oopoos.sean@gmail.com"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        company_tickers = pd.DataFrame.from_dict(response.json(), orient='index')
        company_tickers['cik_str'] = company_tickers['cik_str'].astype(str).str.zfill(10)
        matched_row = company_tickers[company_tickers['title'].str.contains(english_name, case=False, na=False)]
        if not matched_row.empty:
            return matched_row.iloc[0]['cik_str']
    return None

# Function to get 10-K URL
def get_10k_url(cik):
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    headers = {"User-Agent": "oopoos.sean@gmail.com"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        for i, form in enumerate(data["filings"]["recent"]["form"]):
            if form == "10-K":
                accession_number = data["filings"]["recent"]["accessionNumber"][i].replace("-", "")
                primary_document = data["filings"]["recent"]["primaryDocument"][i]
                return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number}/{primary_document}"
    return None

# Function to summarize text from 10-K
def summarize_10k(url):
    headers = {"User-Agent": "oopoos.sean@gmail.com"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator="\n")

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an assistant that summarizes text in Korean."},
                {"role": "user", "content": f"""Analyze the following 10-K document. Summarize the most important parts that investors focus on when evaluating a company in Korean. Specifically:
                        1. Business overview (Item 1), including revenue streams and competitive advantages.
                        2. Risk factors (Item 1A) and how they may impact the company.
                        3. Legal proceedings (Item 3) that could affect the company’s operations.
                        4. Key insights from Management’s Discussion and Analysis (MD&A) (Item 7).
                        5. Critical financial data (Item 8) from income statements, balance sheets, and cash flow statements.
                        6. Equity and shareholder-related matters (Item 5), such as dividends or stock buybacks.
                        7. Information about directors and executive officers (Item 10), including their strategies and governance.
                        8. Any unique competitive advantages or potential red flags for the company.
                        Ensure the summary is concise and focused on key takeaways.:\n\n{text}"""}
            ],
        )

        return completion.choices[0].message.content
    return "요약 실패: 데이터를 처리할 수 없습니다."


# Streamlit UI
st.title("미국 회사 정보 제공 서비스")
company_name = st.text_input("회사 이름을 입력하세요 (한글로):")

if st.button("검색"):
    if company_name:
        st.write(f"찾는 회사 이름(한글): {company_name}")
        english_name = translate_name_to_english(company_name)
        st.write(f"찾는 회사 이름(영문): {english_name}")

        cik = get_cik(company_name)
        if cik:
            with st.spinner("10-K 요약 중입니다. 잠시만 기다려주세요..."):
                summary = summarize_10k(cik)
            st.success("요약 완료!")
            st.write("### 회사 정보 요약")
            st.write(summary)
        else:
            st.error("해당 회사의 CIK를 찾을 수 없습니다.")
    else:
        st.warning("회사 이름을 입력해주세요.")

