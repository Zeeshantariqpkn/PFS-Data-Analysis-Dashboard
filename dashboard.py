import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re

# Page configuration
st.set_page_config(
    page_title="PFS Data Analysis Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2rem;
        color: #2c3e50;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
    }
    .improvement {
        color: #27ae60;
        font-weight: bold;
    }
    .decrease {
        color: #e74c3c;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# Domain configuration
DOMAINS = {
    "Family Functioning": {"sheet": "Family Functioning", "color": "#3498db", "items": 3},
    "Nurturing/Attachment": {"sheet": "Nurturing", "color": "#2ecc71", "items": 4},
    "Social Support": {"sheet": "Social Support", "color": "#e74c3c", "items": 5},
    "Relationship with Practitioner": {"sheet": "Practitioner", "color": "#9b59b6", "items": 3},
    "Concrete": {"sheet": "Concrete", "color": "#f39c12", "items": 4}
}

@st.cache_data
def parse_pfs_data(uploaded_file):
    """Parse PFS Excel file and extract all data"""
    try:
        excel_file = pd.ExcelFile(uploaded_file)
        all_data = {}
        
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=None)
            all_data[sheet_name] = df
            
        # Extract summary data
        summary_data = {}
        if "Summary" in all_data:
            summary_df = all_data["Summary"]
            # Extract pre and post values from Summary sheet
            for domain in DOMAINS.keys():
                for idx in range(len(summary_df)):
                    row = summary_df.iloc[idx]
                    if domain in str(row.values[0]):
                        # Get Before and After values
                        before_val = None
                        after_val = None
                        if len(row) > 1:
                            before_val = row.iloc[1] if pd.notna(row.iloc[1]) else None
                        if len(row) > 2:
                            after_val = row.iloc[2] if pd.notna(row.iloc[2]) else None
                        
                        # Convert to float if possible
                        if before_val is not None:
                            try:
                                before_val = float(before_val)
                            except:
                                before_val = None
                        if after_val is not None:
                            try:
                                after_val = float(after_val)
                            except:
                                after_val = None
                        
                        if before_val is not None or after_val is not None:
                            summary_data[domain] = {
                                "Pre": before_val if before_val is not None else 0,
                                "Post": after_val if after_val is not None else 0
                            }
                        break
        
        # Extract detailed data for each domain
        detailed_data = {}
        
        for domain, config in DOMAINS.items():
            sheet_name = config["sheet"]
            if sheet_name in all_data:
                df = all_data[sheet_name]
                domain_info = extract_domain_data(df, domain, config["items"])
                if domain_info:
                    detailed_data[domain] = domain_info
        
        return summary_data, detailed_data, all_data
    except Exception as e:
        st.error(f"Error parsing file: {str(e)}")
        return {}, {}, {}

def extract_domain_data(df, domain_name, num_items):
    """Extract pre and post data for a specific domain"""
    try:
        # Find subscale values (usually at the bottom of the sheet)
        pre_value = None
        post_value = None
        pre_total = None
        post_total = None
        
        for idx in range(len(df) - 10, len(df)):
            if idx >= 0:
                row = df.iloc[idx]
                row_text = ' '.join([str(x) for x in row.values if pd.notna(x)]).lower()
                
                # Look for Before/After indicators
                if 'before:' in row_text or 'subscale' in row_text:
                    # Try to find numeric values
                    for col in range(len(row)):
                        val = row.iloc[col]
                        if pd.notna(val) and isinstance(val, (int, float)):
                            if pre_value is None:
                                pre_value = val
                            elif post_value is None:
                                post_value = val
        
        # Look for Total rows with sums
        for idx in range(len(df)):
            row = df.iloc[idx]
            for col in range(len(row)):
                if pd.notna(row.iloc[col]) and 'total' in str(row.iloc[col]).lower():
                    # Look for sum values nearby
                    if col + 1 < len(row) and pd.notna(row.iloc[col + 1]):
                        try:
                            total_val = float(row.iloc[col + 1])
                            if pre_total is None:
                                pre_total = total_val
                            elif post_total is None:
                                post_total = total_val
                        except:
                            pass
        
        # Extract individual responses if available
        pre_responses = []
        post_responses = []
        
        # Look for response columns
        for idx in range(min(200, len(df))):
            row = df.iloc[idx]
            row_text = ' '.join([str(x) for x in row.values if pd.notna(x)]).lower()
            
            if 'responses' in row_text or 'weight' in row_text:
                # This might be a header row
                continue
            
            # Look for numeric response patterns
            numeric_vals = [x for x in row.values if pd.notna(x) and isinstance(x, (int, float)) and 0 <= x <= 4]
            if len(numeric_vals) >= num_items:
                if len(pre_responses) < 20:  # Limit to reasonable number
                    pre_responses.append(numeric_vals[:num_items])
                elif len(post_responses) < 20:
                    post_responses.append(numeric_vals[:num_items])
        
        # Calculate means if we have responses
        pre_mean = np.mean([sum(r) / len(r) for r in pre_responses]) if pre_responses else pre_value
        post_mean = np.mean([sum(r) / len(r) for r in post_responses]) if post_responses else post_value
        
        # Use totals if available
        if pre_total and not pre_mean:
            pre_mean = pre_total / num_items if num_items > 0 else pre_total
        if post_total and not post_mean:
            post_mean = post_total / num_items if num_items > 0 else post_total
        
        if pre_mean is not None or post_mean is not None:
            return {
                "pre_mean": pre_mean if pre_mean is not None else 0,
                "post_mean": post_mean if post_mean is not None else 0,
                "pre_responses": pre_responses,
                "post_responses": post_responses,
                "num_items": num_items
            }
        
        return None
    except Exception as e:
        st.warning(f"Error extracting {domain_name} data: {str(e)}")
        return None

def create_comparison_chart(summary_data):
    """Create comparison bar chart"""
    if not summary_data:
        return None
    
    domains = list(summary_data.keys())
    pre_values = [summary_data[d].get("Pre", 0) for d in domains]
    post_values = [summary_data[d].get("Post", 0) for d in domains]
    
    fig = go.Figure(data=[
        go.Bar(name='Pre', x=domains, y=pre_values, marker_color='#3498db', text=[f"{x:.2f}" for x in pre_values], textposition='auto'),
        go.Bar(name='Post', x=domains, y=post_values, marker_color='#e74c3c', text=[f"{x:.2f}" for x in post_values], textposition='auto')
    ])
    
    fig.update_layout(
        title="Pre vs Post Scores by Domain",
        barmode='group',
        xaxis_title="Domain",
        yaxis_title="Score",
        height=500,
        hovermode='x unified',
        yaxis_range=[0, 4]
    )
    
    return fig

def create_improvement_chart(detailed_data):
    """Create improvement percentage chart"""
    if not detailed_data:
        return None
    
    domains = []
    improvements = []
    colors = []
    
    for domain, data in detailed_data.items():
        pre = data.get("pre_mean", 0)
        post = data.get("post_mean", 0)
        if pre > 0:
            improvement = ((post - pre) / pre) * 100
            domains.append(domain)
            improvements.append(improvement)
            colors.append('#27ae60' if improvement > 0 else '#e74c3c')
    
    if not domains:
        return None
    
    fig = go.Figure(data=[
        go.Bar(x=domains, y=improvements, marker_color=colors, 
               text=[f"{x:+.1f}%" for x in improvements], textposition='outside')
    ])
    
    fig.update_layout(
        title="Improvement Percentage by Domain",
        xaxis_title="Domain",
        yaxis_title="Percentage Change (%)",
        height=450,
        showlegend=False
    )
    
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=2)
    
    return fig

def create_radar_chart(detailed_data):
    """Create radar chart"""
    if not detailed_data:
        return None
    
    domains = []
    pre_scores = []
    post_scores = []
    
    for domain, data in detailed_data.items():
        domains.append(domain)
        pre_scores.append(data.get("pre_mean", 0))
        post_scores.append(data.get("post_mean", 0))
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=pre_scores,
        theta=domains,
        fill='toself',
        name='Pre',
        line_color='#3498db',
        fillcolor='rgba(52, 152, 219, 0.3)'
    ))
    
    fig.add_trace(go.Scatterpolar(
        r=post_scores,
        theta=domains,
        fill='toself',
        name='Post',
        line_color='#e74c3c',
        fillcolor='rgba(231, 76, 60, 0.3)'
    ))
    
    fig.update_layout(
        title="Domain Scores Comparison - Radar Chart",
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 4]
            )),
        showlegend=True,
        height=550
    )
    
    return fig

def create_individual_chart(detailed_data, domain):
    """Create individual response visualization"""
    if domain not in detailed_data:
        return None
    
    data = detailed_data[domain]
    pre_responses = data.get("pre_responses", [])
    post_responses = data.get("post_responses", [])
    
    if not pre_responses and not post_responses:
        return None
    
    # Calculate individual scores
    pre_scores = [sum(r) / len(r) for r in pre_responses] if pre_responses else []
    post_scores = [sum(r) / len(r) for r in post_responses] if post_responses else []
    
    # Create comparison
    max_len = max(len(pre_scores), len(post_scores))
    participants = [f"P{i+1}" for i in range(max_len)]
    
    # Pad lists to same length
    pre_scores_padded = pre_scores + [None] * (max_len - len(pre_scores))
    post_scores_padded = post_scores + [None] * (max_len - len(post_scores))
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=participants,
        y=pre_scores_padded,
        mode='lines+markers',
        name='Pre',
        line=dict(color='#3498db', width=2),
        marker=dict(size=8)
    ))
    
    fig.add_trace(go.Scatter(
        x=participants,
        y=post_scores_padded,
        mode='lines+markers',
        name='Post',
        line=dict(color='#e74c3c', width=2),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        title=f"{domain} - Individual Participant Scores",
        xaxis_title="Participant",
        yaxis_title="Score",
        height=450,
        hovermode='closest'
    )
    
    return fig

# Main app
st.markdown('<div class="main-header">📊 PFS Data Analysis Dashboard</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/bar-chart.png", width=80)
    st.title("Navigation")
    
    uploaded_file = st.file_uploader(
        "Upload Excel File",
        type=['xlsx', 'xls'],
        help="Upload the PFS data Excel file"
    )
    
    st.markdown("---")
    st.markdown("### Dashboard Views")
    view_option = st.radio(
        "Select View",
        ["📈 Main Dashboard", "📋 Single Sheet Analysis", "📊 Domain Comparison", "👥 Individual Analysis"]
    )
    
    st.markdown("---")
    st.markdown("### About")
    st.info(
        "This dashboard analyzes Protective Factors Survey (PFS) data to track "
        "improvements across key domains."
    )

if uploaded_file is not None:
    with st.spinner("Loading and analyzing data..."):
        summary_data, detailed_data, all_sheets = parse_pfs_data(uploaded_file)
    
    if summary_data or detailed_data:
        if view_option == "📈 Main Dashboard":
            st.markdown("## 🎯 Key Metrics Overview")
            
            # Calculate overall metrics
            col1, col2, col3, col4 = st.columns(4)
            
            total_pre = 0
            total_post = 0
            domain_count = 0
            
            for domain, data in detailed_data.items():
                if data.get("pre_mean", 0) > 0 or data.get("post_mean", 0) > 0:
                    total_pre += data.get("pre_mean", 0)
                    total_post += data.get("post_mean", 0)
                    domain_count += 1
            
            if domain_count > 0:
                avg_pre = total_pre / domain_count
                avg_post = total_post / domain_count
                overall_change = avg_post - avg_pre
                overall_percent = (overall_change / avg_pre * 100) if avg_pre > 0 else 0
                
                with col1:
                    st.metric("Average Pre Score", f"{avg_pre:.2f}")
                with col2:
                    st.metric("Average Post Score", f"{avg_post:.2f}")
                with col3:
                    st.metric("Average Change", f"{overall_change:+.2f}")
                with col4:
                    st.metric("Average % Change", f"{overall_percent:+.1f}%")
            
            st.markdown("---")
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                comp_chart = create_comparison_chart(summary_data if summary_data else detailed_data)
                if comp_chart:
                    st.plotly_chart(comp_chart, use_container_width=True)
            
            with col2:
                imp_chart = create_improvement_chart(detailed_data)
                if imp_chart:
                    st.plotly_chart(imp_chart, use_container_width=True)
            
            # Radar chart
            radar_chart = create_radar_chart(detailed_data)
            if radar_chart:
                st.plotly_chart(radar_chart, use_container_width=True)
            
            # Detailed metrics table
            st.markdown("## 📊 Detailed Domain Metrics")
            
            metrics_data = []
            for domain, data in detailed_data.items():
                pre = data.get("pre_mean", 0)
                post = data.get("post_mean", 0)
                change = post - pre
                percent_change = (change / pre * 100) if pre > 0 else 0
                
                metrics_data.append({
                    "Domain": domain,
                    "Pre Score": f"{pre:.3f}",
                    "Post Score": f"{post:.3f}",
                    "Absolute Change": f"{change:+.3f}",
                    "% Change": f"{percent_change:+.1f}%",
                    "Status": "✅ Improving" if change > 0 else "⚠️ Needs Attention" if change < 0 else "➡️ Stable"
                })
            
            if metrics_data:
                metrics_df = pd.DataFrame(metrics_data)
                st.dataframe(metrics_df, use_container_width=True, hide_index=True)
            
            # Summary statistics
            st.markdown("## 📈 Summary Statistics")
            
            total_pre_respondents = sum([len(data.get("pre_responses", [])) for data in detailed_data.values()])
            total_post_respondents = sum([len(data.get("post_responses", [])) for data in detailed_data.values()])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Pre-Responses", total_pre_respondents)
            with col2:
                st.metric("Total Post-Responses", total_post_respondents)
            with col3:
                st.metric("Domains Analyzed", len(detailed_data))
        
        elif view_option == "📋 Single Sheet Analysis":
            st.markdown("## 📄 Single Sheet Analysis")
            
            sheet_names = list(all_sheets.keys())
            selected_sheet = st.selectbox("Select Sheet to Analyze", sheet_names)
            
            if selected_sheet:
                df = all_sheets[selected_sheet]
                st.markdown(f"### Sheet: {selected_sheet}")
                st.markdown(f"**Dimensions:** {df.shape[0]} rows × {df.shape[1]} columns")
                
                # Display data
                st.markdown("#### Data Preview")
                st.dataframe(df, use_container_width=True)
                
                # Basic statistics
                st.markdown("#### Basic Statistics")
                numeric_data = df.select_dtypes(include=[np.number])
                if not numeric_data.empty:
                    st.dataframe(numeric_data.describe(), use_container_width=True)
        
        elif view_option == "📊 Domain Comparison":
            st.markdown("## 🔍 Domain Comparison Analysis")
            
            if detailed_data:
                selected_domains = st.multiselect(
                    "Select Domains to Compare",
                    options=list(detailed_data.keys()),
                    default=list(detailed_data.keys())
                )
                
                if selected_domains:
                    # Prepare comparison data
                    comparison_data = []
                    for domain in selected_domains:
                        data = detailed_data[domain]
                        comparison_data.append({
                            "Domain": domain,
                            "Pre": data.get("pre_mean", 0),
                            "Post": data.get("post_mean", 0),
                            "Change": data.get("post_mean", 0) - data.get("pre_mean", 0),
                            "% Change": ((data.get("post_mean", 0) - data.get("pre_mean", 0)) / data.get("pre_mean", 1) * 100) if data.get("pre_mean", 0) > 0 else 0
                        })
                    
                    comp_df = pd.DataFrame(comparison_data)
                    
                    # Bar chart
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name='Pre', x=comp_df['Domain'], y=comp_df['Pre'], marker_color='#3498db'))
                    fig.add_trace(go.Bar(name='Post', x=comp_df['Domain'], y=comp_df['Post'], marker_color='#e74c3c'))
                    fig.update_layout(barmode='group', title="Domain Score Comparison", height=450)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Display table
                    st.dataframe(comp_df, use_container_width=True, hide_index=True)
            else:
                st.warning("No detailed data available for comparison")
        
        elif view_option == "👥 Individual Analysis":
            st.markdown("## 👥 Individual Participant Analysis")
            
            if detailed_data:
                selected_domain = st.selectbox("Select Domain", list(detailed_data.keys()))
                
                if selected_domain:
                    ind_chart = create_individual_chart(detailed_data, selected_domain)
                    if ind_chart:
                        st.plotly_chart(ind_chart, use_container_width=True)
                    
                    # Show response distribution
                    data = detailed_data[selected_domain]
                    pre_responses = data.get("pre_responses", [])
                    post_responses = data.get("post_responses", [])
                    
                    if pre_responses:
                        st.markdown("#### Pre-Response Distribution")
                        pre_flat = [val for response in pre_responses for val in response]
                        fig_pre = px.histogram(pre_flat, nbins=5, range_x=[0, 4], title="Pre-Response Value Distribution")
                        st.plotly_chart(fig_pre, use_container_width=True)
                    
                    if post_responses:
                        st.markdown("#### Post-Response Distribution")
                        post_flat = [val for response in post_responses for val in response]
                        fig_post = px.histogram(post_flat, nbins=5, range_x=[0, 4], title="Post-Response Value Distribution")
                        st.plotly_chart(fig_post, use_container_width=True)
            else:
                st.warning("No individual response data available")
        
        # Export section
        st.markdown("---")
        st.markdown("## 📥 Export Analysis")
        
        if detailed_data:
            export_data = []
            for domain, data in detailed_data.items():
                export_data.append({
                    "Domain": domain,
                    "Pre_Mean": data.get("pre_mean", 0),
                    "Post_Mean": data.get("post_mean", 0),
                    "Change": data.get("post_mean", 0) - data.get("pre_mean", 0),
                    "N_Pre": len(data.get("pre_responses", [])),
                    "N_Post": len(data.get("post_responses", []))
                })
            
            export_df = pd.DataFrame(export_data)
            csv = export_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Analysis Report (CSV)",
                data=csv,
                file_name="pfs_analysis_report.csv",
                mime="text/csv",
                use_container_width=True
            )
    else:
        st.error("No data could be extracted from the uploaded file. Please check the file format.")
else:
    st.info("👈 Please upload a PFS Excel file to begin the analysis")
    
    st.markdown("""
    ### 📋 Instructions
    
    1. **Upload** your PFS Excel file using the sidebar uploader
    2. **Navigate** through different analysis views
    3. **Export** your results for reporting
    
    ### 📊 Supported Domains
    
    - Family Functioning
    - Nurturing/Attachment
    - Social Support
    - Relationship with Practitioner
    - Concrete Supports
    """)
