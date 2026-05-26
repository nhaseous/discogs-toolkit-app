class FormattedEntry: # Formatted marketplace entry for a single release and its listings

    def __init__(self,title,url,imgUrl,listings,place,total,lastSold,daysAgo,yearsAgo=None,index=0,price_badges="",listing_ids=None,reprice_data=None):
        self.title = title
        self.url = url
        self.imgUrl = imgUrl
        self.listings = listings
        self.place = place
        self.total = total
        self.lastSold = lastSold
        self.daysAgo = daysAgo
        self.yearsAgo = yearsAgo
        self.index = index
        self.price_badges = price_badges
        self.listing_ids = listing_ids if listing_ids is not None else []
        self.reprice_data = reprice_data if reprice_data is not None else []
