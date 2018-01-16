# Land Surface Temperature
Tom M Logan  
www.tomlogan.co.nz

## Description:
Understanding the factors influencing urban land surface temperature during the night and day.

## Cities analysed:
* [x] Baltimore (bal)
* [ ] Chicago (chi)
* [ ] Detroit (det)
* [ ] Phoenix (phx)
* [ ] Portland (por)

Maybe will add a couple of cities from non-industrialized countries to see if the results are generalizable?
* [ ] Accra, Ghana (acr) - I'm not sure if the sat images are clear enough
* [ ] Kolkata, India (kol)
* [ ] Manila, Philippines (man)

## Steps:
1. Process the LandSat images to land surface temperatures

## 1. LandSat images to LST, albedo, and NDVI:


#### 1.1 Download the satellite images
  1. Website: https://earthexplorer.usgs.gov/
  2. Enter Search Criteria:
    1. Address/Place - type the city name and state, e.g. 'Baltimore, MD' - click on the correct address and it should appear on the map.
    2. Date Range - we want to use summer dates
        I'm looking at years 2013-2017 and use months of May (05) - September (09) inclusive
        Need to find images that don't have too much cloud cover.
  3. Data Sets
    1. Select Landsat -> Landsat Collection 1 Level-1 -> Landsat 8 OLI/TIRS C1 Level-1
  4. Additional Criteria
    1. Sensor Identifier: OLI_TIRS
    2. Data type level-1: All
    3. Day/Night Indicator: Select relevant
    4. Cloud Cover: I leave these blank because I care about the cloud cover of the city, rather than the image and it's possible to have an image with high cloud cover but a clear sky above the city.
  5. View each image in turn and select ones with low cloud cover of the city

    When an image is selected
    * downloaded the Level-1 GeoTIFF Data Product
    * added to the `data/raw` directory

#### 1.2 Metadata
  `metadata.csv` in `/data` provides information from each of the raw satellite images necessary for them to be processed.
  1. df

#### 1.3 Process satellite images to LST, albedo, NDVI
  1. df

#### 1.4 Calculate average of LST, albedo, NDVI
  1. df


## 2. Statistical inference on the dataset:

TBD

## Markdown Cheatsheet
*markdown cheat sheet: https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet*

#### Temporary example markdown:

    An indent will write in code

1. Lists

    Note: use tabs to indent new writing

3. Write code chunks

    Here is some Python code:

    ```python
    >>> print("Hello world!")
    Hello world!
    ```

    ```R
    >>> for (i in x){
    Hello world!
  }
    ```

4. Install ipymd:

    To install the latest release version:

    ```shell
    pip install ipymd
    ```

    Alternatively, to install the development version:

    ```shell
    pip install git+https://github.com/rossant/ipymd
    ```

6. Images

    Add an image like this

    ![image](https://cloud.githubusercontent.com/assets/1942359/5570181/f656a484-8f7d-11e4-8ec2-558d022b13d3.png)

7. Checkboxes
    * [ ] Checkboxes are available for issues or steps
    * [x] You can click it in the markdown preview

5. Tables

    Table 1: example table

| Tables        | Are           | Cool  |
| ------------- |:-------------:| -----:|
| col 3 is      | right-aligned | $1600 |
| col 2 is      | centered      |   $12 |
| zebra stripes | are neat      |    $1 |