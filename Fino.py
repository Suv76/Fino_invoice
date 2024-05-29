import streamlit as st
import pandas as pd
import io

# Function to process the data
def process_data(data_file, btcd_file, smfl_file):
    # Read the files
    data = pd.read_excel(data_file, sheet_name="transactions")
    BTCD = pd.read_excel(btcd_file)
    smfl_data = pd.read_excel(smfl_file, skiprows=3)
    smfl_data = smfl_data.iloc[:-1]

    data['agent_id_login'] = data['ZRFUT1'].str.extract('(\d+)')
    position = data.columns.get_loc('ZRFUT1') + 1
    data.insert(position, 'agent_id_login', data.pop('agent_id_login'))

    non_integer_values = BTCD['Branch ID'].loc[~BTCD['Branch ID'].astype(str).str.isdigit()]
    BTCD['Branch ID'].fillna(0, inplace=True)
    BTCD['Branch ID'] = BTCD['Branch ID'].astype(int, errors='ignore')
    BTCD['Branch ID'] = BTCD['Branch ID'].astype(str)

    data['ZRFUT6'] = data['ZRFUT6'].astype(str)

    merged_data = pd.merge(data, BTCD[['Branch ID', 'State']], left_on='ZRFUT6', right_on='Branch ID', how='left')
    data['New State'] = merged_data['State_y']

    null_values = data['New State'].isnull()
    num_null_values = null_values.sum()

    merged_data1 = pd.merge(data, smfl_data[['Employee_Code', 'State']], left_on='agent_id_login', right_on='Employee_Code', how='left')
    nan_rows = data['New State'].isnull()
    data.loc[nan_rows, 'New State'] = merged_data1.loc[nan_rows, 'State_y']
    null_values = data['New State'].isnull()

    # Create a dictionary to hold DataFrames for each state
    state_dfs = {}
    unique_states = data['New State'].unique()
    states_with_both_channels = []

    for state in unique_states:
        state_df = data[data['New State'] == state]
        branch_df = state_df[state_df['channel'] == 'Branch']
        merchant_df = state_df[state_df['channel'] == 'Merchant']
        
        if not branch_df.empty and not merchant_df.empty:
            states_with_both_channels.append(state)
            state_dfs[state + '-Branch'] = branch_df
            state_dfs[state + '-Merchant'] = merchant_df
        else:
            if not branch_df.empty:
                state_dfs[state] = branch_df
            if not merchant_df.empty:
                state_dfs[state] = merchant_df

    state_sums = {}
    state_counts = {}

    for state, df in state_dfs.items():
        state_sums[state] = df['Amount'].sum()
        state_counts[state] = df['Amount'].count()

    summary_table_data = []

    for state, df in state_dfs.items():
        if '-' in state:
            state_name, channel = state.split('-')
        else:
            state_name = state
            channel = 'Branch' if state_name in states_with_both_channels else 'Merchant'
        
        if channel == 'Branch':
            calculated_revenue = [amount * 0.0015 + 0.18 * (amount * 0.0015) for amount in df['Amount']]
        else:
            calculated_revenue = [amount * 0.0025 + 0.18 * (amount * 0.0025) for amount in df['Amount']]
        
        summary_table_data.append({
            'New State': state_name,
            'Channel': channel,
            'Count of Amount': state_counts[state],
            'Sum of Amount': state_sums[state],
            'Sum of calculated_revenue': sum(calculated_revenue)
        })

    summary_table = pd.DataFrame(summary_table_data)
    total_count = summary_table['Count of Amount'].sum()
    total_sum_amount = summary_table['Sum of Amount'].sum()
    total_sum_calculated_revenue = summary_table['Sum of calculated_revenue'].sum()

    total_row = pd.DataFrame({
        'New State': ['Total'],
        'Channel': '',
        'Count of Amount': total_count,
        'Sum of Amount': total_sum_amount,
        'Sum of calculated_revenue': total_sum_calculated_revenue
    }, index=[len(summary_table)])

    summary_table_with_total = pd.concat([summary_table, total_row])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_table_with_total.to_excel(writer, index=False, sheet_name='Summary')
        for state, df in state_dfs.items():
            if '-' in state:
                sheet_name = state
            else:
                sheet_name = state if state in states_with_both_channels else state.split('-')[0]
            df.to_excel(writer, index=False, sheet_name=sheet_name)
    
    output.seek(0)
    return output

# Streamlit UI
st.title("Fino Split Data Processing")

data_file = st.file_uploader("Upload the data file", type=["xlsx"])
btcd_file = st.file_uploader("Upload the BTCD file", type=["xlsx"])
smfl_file = st.file_uploader("Upload the SMFL data file", type=["xlsx"])

if st.button("Generate Output") and data_file and btcd_file and smfl_file:
    output = process_data(data_file, btcd_file, smfl_file)
    st.success("Data processed successfully. Click the button below to download the output.")
    st.download_button(
        label="Download Output",
        data=output,
        file_name="fino_split.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
