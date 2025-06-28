import streamlit as st
import json 
import requests
from PIL import Image

# Create a title for the web app.
st.title("FB Marketplace scraper")

# Add a list of supported cities.
supported_cities = ["Arlington", "Baltimore", "Salt Lake City", "Provo"]

# Take user input for the city, query, and max price.
city = st.selectbox("City", supported_cities, index=supported_cities.index("Salt Lake City"))
query = st.text_input("Query", "Car")
min_price = st.text_input("Min Price", "0")
max_price = st.text_input("Max Price", "10000")
max_miles = st.text_input("Max Miles", "100000")

# Create a button to submit the form.
submit = st.button("Submit")

# If the button is clicked.
if submit:
    # TODO - Remove any commas from the max_price before sending the request.
    if "," in max_price:
        max_price = max_price.replace(",", "")
    if "," in min_price:
        min_price = min_price.replace(",", "")
    else:
        pass
    res = requests.get(f"http://127.0.0.1:8000/crawl_facebook_marketplace?city={city}&query={query}&max_price={max_price}&min_price={min_price}"
    )
    
    # Convert the response from json into a Python list.
    results = res.json()
    
    # Display the length of the results list.
    st.write(f"Number of results: {len(results)}")
    
    # Iterate over the results list to display each item.
    for item in results:
        try:
            miles = item["miles"]
            cleaned_miles = miles.replace("K", "000")
            if int(cleaned_miles) > int(max_miles):
                continue
        except KeyError:
            miles = "Miles not found"
        st.header(item["title"])
        img_url = item["image"]
        st.image(img_url, width=200)
        st.write(item["price"])
        st.write(item["location"])
        st.write(miles)
        st.write(f"https://www.facebook.com{item['link']}")
        st.write("----")
    

      


